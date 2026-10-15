"""Messages sent by native/gg_hook over loopback UDP.

Each datagram is one UTF-8 line of tab-separated fields starting with a
version tag. Keep in sync with native/gg_hook/src (reporter.h, dllmain.cpp,
tooltip_hook.cpp).
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROTOCOL_TAG = "GG1"
DEFAULT_PORT = 47817  # reporter.h: kReporterPort

ITEM_FIELDS = (
    "calls",
    "seed",
    "base_record",
    "prefix_record",
    "suffix_record",
    "modifier_record",
    "materia_record",
    "relic_bonus",
    "enchantment_record",
    "transmute_record",
    "ascendant_1",
    "ascendant_2",
)


@dataclass(frozen=True, slots=True)
class HookStatus:
    """A ``hello`` (sent once after install) or ``heartbeat`` (every 5s)."""

    kind: str
    pid: int
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HookError:
    detail: str


# GAME::GameTextClass values observed in Grim Dawn 1.3.1. Relative to IA's
# documented enum they are shifted up by one around the item stats and by two
# around the component section, with new ones such as 0x42 (item type line)
# and 0x51 (skill bonus). Unknown classes are shown by number.
ITEM_NAME_TEXT_CLASSES = frozenset(range(0x02, 0x08))
TEXT_CLASS_NAMES = {
    **{text_class: "name" for text_class in ITEM_NAME_TEXT_CLASSES},
    0x12: "base stats",
    0x13: "bonuses",
    0x14: "requirements",
    0x1D: "component",
    0x1F: "component label",
    0x21: "component bonus",
    0x23: "hint",
    0x42: "item type",
    0x51: "skill bonus",
}


@dataclass(frozen=True, slots=True)
class TooltipLine:
    text_class: int
    text: str

    @property
    def class_name(self) -> str:
        return TEXT_CLASS_NAMES.get(self.text_class, f"class {self.text_class}")


@dataclass(frozen=True, slots=True)
class HoveredItem:
    """The records and seed of an item whose tooltip the game just built."""

    calls: int
    seed: int
    base_record: str
    prefix_record: str = ""
    suffix_record: str = ""
    modifier_record: str = ""
    materia_record: str = ""
    relic_bonus: str = ""
    enchantment_record: str = ""
    transmute_record: str = ""
    ascendant_1: str = ""
    ascendant_2: str = ""
    # The tooltip text the game just built, with the rolled values.
    lines: tuple[TooltipLine, ...] = ()
    # The DLL's own evaluation, sent as "@key=value" fields: grade, score,
    # matched, total, rq ("-" when none), label, rarity, table (grade table
    # id), detail (1 if lines came from the detailed pass), injected.
    attributes: dict[str, str] = field(default_factory=dict)

    @property
    def records(self) -> tuple[str, str, str]:
        return (self.base_record, self.prefix_record, self.suffix_record)


@dataclass(frozen=True, slots=True)
class FilterDecision:
    """The loot filter hid (or let through) a ground item."""

    seed: int
    base_record: str
    prefix_record: str
    suffix_record: str
    grade: str
    rarity_class: str
    hidden: bool
    table_id: str


HookMessage = HookStatus | HookError | HoveredItem | FilterDecision


class ProtocolError(ValueError):
    """A datagram that is not a valid gg_hook message."""


def parse_message(payload: bytes) -> HookMessage:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProtocolError("message is not UTF-8") from error
    fields = text.rstrip("\r\n").split("\t")
    if not fields or fields[0] != PROTOCOL_TAG:
        raise ProtocolError(f"unknown protocol tag: {fields[0] if fields else ''!r}")
    if len(fields) < 2:
        raise ProtocolError("message has no kind")
    kind, values = fields[1], fields[2:]
    try:
        if kind in {"hello", "heartbeat"}:
            if len(values) != 3:
                raise ProtocolError(f"{kind} expects 3 fields, got {len(values)}")
            return HookStatus(kind, int(values[0]), values[1] == "ok", values[2])
        if kind == "error":
            return HookError("\t".join(values))
        if kind == "item":
            if len(values) < len(ITEM_FIELDS):
                raise ProtocolError(
                    f"item expects at least {len(ITEM_FIELDS)} fields, got {len(values)}"
                )
            raw = dict(zip(ITEM_FIELDS, values))
            extras = values[len(ITEM_FIELDS) :]
            attributes = dict(
                value[1:].partition("=")[::2] for value in extras if value.startswith("@")
            )
            return HoveredItem(
                calls=int(raw.pop("calls")),
                seed=int(raw.pop("seed")),
                lines=tuple(
                    _parse_line(value) for value in extras if not value.startswith("@")
                ),
                attributes=attributes,
                **{key: value.strip() for key, value in raw.items()},
            )
        if kind == "filter":
            if len(values) != 8:
                raise ProtocolError(f"filter expects 8 fields, got {len(values)}")
            return FilterDecision(
                seed=int(values[0]),
                base_record=values[1],
                prefix_record=values[2],
                suffix_record=values[3],
                grade=values[4],
                rarity_class=values[5],
                hidden=values[6] == "1",
                table_id=values[7],
            )
    except ValueError as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError(f"malformed {kind} message: {error}") from error
    raise ProtocolError(f"unknown message kind: {kind!r}")


def _parse_line(value: str) -> TooltipLine:
    text_class, separator, text = value.partition(":")
    if not separator:
        raise ProtocolError(f"tooltip line has no class: {value!r}")
    return TooltipLine(int(text_class), text)
