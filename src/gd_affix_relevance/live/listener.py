"""Print what the in-game hook reports (phase 1: "Got the info")."""

from __future__ import annotations

import re
import socket
from collections.abc import Callable
from dataclasses import dataclass, field

from gd_affix_relevance.live.protocol import (
    DEFAULT_PORT,
    HookError,
    HookMessage,
    HookStatus,
    HoveredItem,
    ITEM_NAME_TEXT_CLASSES,
    ProtocolError,
    parse_message,
)


# Colour codes appear as {^E} in localization files and as a bare ^E in
# tooltip text.
COLOR_CODE = re.compile(r"\{\^.\}|\^[A-Za-z]")
# The item name is already in the header line.
SKIPPED_TEXT_CLASSES = ITEM_NAME_TEXT_CLASSES


def plain_text(text: str) -> str:
    """Strip Grim Dawn colour codes such as {^E}."""

    return COLOR_CODE.sub("", text).strip()


def _normalize_record(path: str) -> str:
    return path.strip().replace("\\", "/").casefold()


@dataclass
class RecordNames:
    """Record path -> display name, built from the compiled catalog."""

    items: dict[str, tuple[str, str]] = field(default_factory=dict)
    affixes: dict[str, tuple[str, str]] = field(default_factory=dict)

    @classmethod
    def from_catalog(cls, bundle: object) -> RecordNames:
        names = cls()
        for item in bundle.items.all_items():  # type: ignore[attr-defined]
            for variant in item.variants:
                names.items[_normalize_record(variant.record_path)] = (
                    item.display_name,
                    variant.rarity,
                )
        for affix in bundle.affixes.affixes:  # type: ignore[attr-defined]
            for tier in affix.tiers:
                names.affixes[_normalize_record(tier.record_path)] = (
                    affix.display_name,
                    affix.rarity,
                )
        return names

    def item(self, record: str) -> tuple[str, str] | None:
        return self.items.get(_normalize_record(record)) if record else None

    def affix(self, record: str) -> tuple[str, str] | None:
        return self.affixes.get(_normalize_record(record)) if record else None


def _item_quality(base_rarity: str, affix_rarities: list[str]) -> str:
    """The quality the game shows: a common base takes its affixes' quality."""

    if base_rarity.casefold() not in {"", "common"}:
        return base_rarity
    if any(rarity.casefold() == "rare" for rarity in affix_rarities):
        return "Rare"
    if affix_rarities:
        return "Magic"
    return base_rarity


def describe_item(item: HoveredItem, names: RecordNames | None = None) -> str:
    names = names or RecordNames()
    affix_records = [record for record in (item.prefix_record, item.suffix_record) if record]
    resolved_affixes = [names.affix(record) for record in affix_records]
    affix_labels = [
        resolved[0] if resolved else record
        for record, resolved in zip(affix_records, resolved_affixes)
    ]
    affix_rarities = [resolved[1] for resolved in resolved_affixes if resolved]

    base = names.item(item.base_record)
    if base is None:
        title = item.base_record or "(no base record)"
    else:
        display_name, rarity = base
        quality = _item_quality(rarity, affix_rarities)
        title = f"{display_name} [{quality}]" if quality else display_name
    text = f"Got the info: {title} (seed {item.seed})"
    if affix_labels:
        text += " with " + " + ".join(affix_labels)
    text += f"  [tooltip builds so far: {item.calls}]"
    stat_lines = [
        f"    {line.class_name:>13} | {plain}"
        for line in item.lines
        if line.text_class not in SKIPPED_TEXT_CLASSES and (plain := plain_text(line.text))
    ]
    return "\n".join([text, *stat_lines])


class ListenerState:
    """Turns hook messages into console lines, suppressing repeat heartbeats."""

    def __init__(self, names: RecordNames | None = None) -> None:
        self.names = names
        self.connected_pid: int | None = None

    def handle(self, message: HookMessage) -> str | None:
        if isinstance(message, HoveredItem):
            return describe_item(message, self.names)
        if isinstance(message, HookError):
            return f"Hook error: {message.detail}"
        if isinstance(message, HookStatus):
            first = message.pid != self.connected_pid
            self.connected_pid = message.pid
            if message.kind == "hello" or first:
                state = "connected" if message.ok else "loaded but NOT hooked"
                detail = message.detail if message.kind == "hello" else (
                    "" if message.ok else "see gg_hook.log"
                )
                suffix = f": {detail}" if detail else ""
                return f"Hook {state} (Grim Dawn pid {message.pid}){suffix}"
        return None


def listen(
    on_line: Callable[[str], None],
    *,
    port: int = DEFAULT_PORT,
    names: RecordNames | None = None,
    should_stop: Callable[[], bool] = lambda: False,
) -> None:
    state = ListenerState(names)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", port))
        sock.settimeout(0.5)
        while not should_stop():
            try:
                payload, _ = sock.recvfrom(65535)
            except TimeoutError:
                continue
            try:
                line = state.handle(parse_message(payload))
            except ProtocolError as error:
                line = f"Ignored malformed message: {error}"
            if line:
                on_line(line)
