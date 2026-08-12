"""Trace concrete items back through loot tables to named drop sources."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.localization_parser import plain_display_name
from gd_affix_relevance.records import RecordRepository, normalize_record_path


# Global loot pools eventually reach hundreds of enemies. Known monster-family
# infrequents currently resolve to at most 21 distinct localized enemy names.
MAX_SPECIFIC_MONSTER_SOURCES = 50
MAX_SPECIFIC_CONTAINER_SOURCES = 10

_CLASSIFICATION_ORDER = {
    "common": 0,
    "champion": 1,
    "hero": 2,
    "quest": 3,
    "boss": 4,
    "superboss": 5,
}


@dataclass(frozen=True, slots=True)
class MonsterDropSource:
    """One distinct, localized enemy name that can drop an item."""

    name: str
    localization_tag: str
    classification: str

    @property
    def rank_key(self) -> tuple[int, str, str]:
        return (
            _CLASSIFICATION_ORDER.get(self.classification.casefold(), 99),
            self.name.casefold(),
            self.localization_tag.casefold(),
        )


@dataclass(frozen=True, slots=True)
class ContainerDropSource:
    """One distinct, localized loot-container name that can drop an item."""

    name: str
    localization_tag: str

    @property
    def rank_key(self) -> tuple[str, str]:
        return self.name.casefold(), self.localization_tag.casefold()


@dataclass(frozen=True, slots=True)
class DropSourceDiscovery:
    monster_sources: dict[str, tuple[MonsterDropSource, ...]]
    container_sources: dict[str, tuple[ContainerDropSource, ...]]


def discover_drop_sources(
    repository: RecordRepository,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
) -> DropSourceDiscovery:
    """Map item paths to bounded enemy and loot-container display names.

    Enemy loot fields and localized loot-container records are independent roots
    in a directed graph of item loot-table DBRs. Sources are propagated through
    that graph to concrete item records. Nodes exceeding the source limit are
    global/random pools and are deliberately omitted rather than presented as
    specific drops.
    """

    loot_children = _loot_graph(repository)

    monster_metadata: dict[str, MonsterDropSource] = {}
    monster_roots: list[tuple[str, str]] = []
    for location in repository.iter_overlaid("records/creatures/enemies"):
        record = repository.load(location)
        source = _monster_source(record, exact_names, folded_names)
        if source is None:
            continue
        source_key = source.name.casefold()
        existing = monster_metadata.get(source_key)
        if existing is None or source.rank_key < existing.rank_key:
            monster_metadata[source_key] = source
        monster_roots.extend(
            _root_references(record, source_key, require_loot_field=True)
        )

    container_metadata: dict[str, ContainerDropSource] = {}
    container_roots: list[tuple[str, str]] = []
    for location in repository.iter_overlaid("records/items/lootchests"):
        record = repository.load(location)
        source = _container_source(record, exact_names, folded_names)
        if source is None:
            continue
        source_key = source.name.casefold()
        existing = container_metadata.get(source_key)
        if existing is None or source.rank_key < existing.rank_key:
            container_metadata[source_key] = source
        container_roots.extend(_root_references(record, source_key))

    return DropSourceDiscovery(
        monster_sources=_propagate_sources(
            loot_children,
            monster_roots,
            monster_metadata,
            MAX_SPECIFIC_MONSTER_SOURCES,
        ),
        container_sources=_propagate_sources(
            loot_children,
            container_roots,
            container_metadata,
            MAX_SPECIFIC_CONTAINER_SOURCES,
        ),
    )


def _loot_graph(repository: RecordRepository) -> dict[str, set[str]]:
    loot_children: dict[str, set[str]] = defaultdict(set)
    for branch in ("records/items/loottables", "records/items/lootchests"):
        for location in repository.iter_overlaid(branch):
            record = repository.load(location)
            loot_children[location.logical_path].update(_item_references(record))
    return loot_children


def _root_references(
    record: RawDbrRecord,
    source_key: str,
    *,
    require_loot_field: bool = False,
) -> list[tuple[str, str]]:
    roots: list[tuple[str, str]] = []
    for field in record.fields:
        if require_loot_field and not field.key.casefold().startswith("loot"):
            continue
        for reference in _references(field.value):
            roots.append((reference, source_key))
    return roots


def _item_references(record: RawDbrRecord) -> set[str]:
    return {
        reference
        for field in record.fields
        for reference in _references(field.value)
    }


def _references(value: str) -> tuple[str, ...]:
    return tuple(
        reference
        for raw_reference in value.split(";")
        if (
            (reference := normalize_record_path(raw_reference)).startswith(
                "records/items/"
            )
            and reference.endswith(".dbr")
        )
    )


def _propagate_sources(
    loot_children: dict[str, set[str]],
    roots: list[tuple[str, str]],
    source_metadata: dict[str, MonsterDropSource | ContainerDropSource],
    max_sources: int,
) -> dict[
    str, tuple[MonsterDropSource | ContainerDropSource, ...]
]:
    """Propagate one kind of named source through the shared loot graph."""

    sources_by_node: dict[str, set[str]] = defaultdict(set)
    pending: deque[str] = deque()
    for reference, source_key in roots:
        if _add_bounded_source(
            sources_by_node[reference], source_key, max_sources
        ):
            pending.append(reference)

    while pending:
        parent = pending.popleft()
        parent_sources = sources_by_node[parent]
        for child in loot_children.get(parent, ()):
            changed = False
            for source_key in parent_sources:
                changed |= _add_bounded_source(
                    sources_by_node[child], source_key, max_sources
                )
            if changed:
                pending.append(child)

    discovered: dict[
        str, tuple[MonsterDropSource | ContainerDropSource, ...]
    ] = {}
    for record_path, source_keys in sources_by_node.items():
        if (
            not record_path.startswith("records/items/")
            or record_path.startswith("records/items/loottables/")
            or record_path.startswith("records/items/lootchests/")
            or not 0 < len(source_keys) <= max_sources
        ):
            continue
        sources = tuple(
            sorted(
                (source_metadata[key] for key in source_keys),
                key=lambda source: source.rank_key,
            )
        )
        discovered[record_path] = sources
    return discovered


def _monster_source(
    record: RawDbrRecord,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
) -> MonsterDropSource | None:
    name_tag = (record.first_value("description") or "").strip()
    if not name_tag:
        return None
    entry = exact_names.get(name_tag) or folded_names.get(name_tag.casefold())
    if entry is None:
        return None
    display_name = plain_display_name(entry.value)
    if not display_name:
        return None
    return MonsterDropSource(
        name=display_name,
        localization_tag=name_tag,
        classification=(record.first_value("monsterClassification") or "").strip(),
    )


def _container_source(
    record: RawDbrRecord,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
) -> ContainerDropSource | None:
    name_tag = (record.first_value("description") or "").strip()
    if not name_tag:
        return None
    entry = exact_names.get(name_tag) or folded_names.get(name_tag.casefold())
    if entry is None:
        return None
    display_name = plain_display_name(entry.value)
    if not display_name:
        return None
    return ContainerDropSource(display_name, name_tag)


def _add_bounded_source(
    target: set[str], source_key: str, max_sources: int
) -> bool:
    if source_key in target or len(target) > max_sources:
        return False
    target.add(source_key)
    return True
