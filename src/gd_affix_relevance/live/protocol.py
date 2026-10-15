"""Messages sent by native/gg_hook over loopback UDP.

Each datagram is one UTF-8 line of tab-separated fields starting with a
version tag. Keep in sync with native/gg_hook/src (reporter.h, dllmain.cpp,
tooltip_hook.cpp).
"""

from __future__ import annotations

from dataclasses import dataclass

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


# GAME::GameTextClass values observed in Grim Dawn 1.3.1. They are IA's
# documented values shifted up by one, plus new ones (0x42 = item type line).
# Unknown classes are shown by number.
ITEM_NAME_TEXT_CLASSES = frozenset(range(0x02, 0x08))
TEXT_CLASS_NAMES = {
    **{text_class: "name" for text_class in ITEM_NAME_TEXT_CLASSES},
    0x12: "base stats",
    0x13: "bonuses",
    0x14: "requirements",
    0x42: "item type",
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


HookMessage = HookStatus | HookError | HoveredItem


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
            return HoveredItem(
                calls=int(raw.pop("calls")),
                seed=int(raw.pop("seed")),
                lines=tuple(
                    _parse_line(value) for value in values[len(ITEM_FIELDS) :]
                ),
                **{key: value.strip() for key, value in raw.items()},
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
