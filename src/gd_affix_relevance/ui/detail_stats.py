"""Build and render the semantic-stat table used by Gear Grades details."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from html import escape

from gd_affix_relevance.scoring import semantic_stat_ids


@dataclass(frozen=True, slots=True)
class DetailStatRow:
    stat_id: str
    label: str
    value: str
    weight: int


def build_detail_stat_rows(
    stat_ids: Iterable[str],
    properties: tuple[object, ...],
    *,
    label_for: Callable[[str], str],
    weight_for: Callable[[str], int],
    property_enabled: Callable[[object], bool] = lambda _property: True,
) -> tuple[DetailStatRow, ...]:
    """Associate scoreable semantic IDs with their concrete catalog values."""

    grouped: dict[str, list[object]] = {}
    for property_ in properties:
        if not property_enabled(property_):
            continue
        for stat_id in semantic_stat_ids(property_):  # type: ignore[arg-type]
            grouped.setdefault(stat_id, []).append(property_)

    rows: list[DetailStatRow] = []
    for stat_id in dict.fromkeys(stat_ids):
        values = tuple(
            dict.fromkeys(
                value
                for property_ in grouped.get(stat_id, ())
                if (value := format_nominal_value(property_))
            )
        )
        if values:
            value = "; ".join(values)
        elif stat_id == "base_weapon_damage_as_physical":
            value = "Implicit"
        elif stat_id.startswith("skill_modifier:"):
            value = "Present"
        else:
            value = "—"
        rows.append(
            DetailStatRow(
                stat_id=stat_id,
                label=label_for(stat_id),
                value=value,
                weight=max(0, min(4, int(weight_for(stat_id)))),
            )
        )
    return tuple(rows)


def format_nominal_value(property_: object) -> str:
    """Format one property's non-jittered, level-selected catalog value."""

    attributes = getattr(property_, "attributes", {})
    if not isinstance(attributes, dict):
        return ""

    if "skill_level" in attributes:
        return _signed(attributes["skill_level"])

    if getattr(property_, "property_id", "") in {
        "damage_conversion",
        "pet_damage_conversion",
    }:
        percent = _percent(attributes.get("percent", ""))
        source = _damage_type(attributes.get("source_damage_type", ""))
        if percent and source:
            return f"{percent} from {source}"
        return percent

    chance = _first_percent(
        attributes,
        "chance_percent",
        "effect_chance_percent",
        "global_chance_percent",
    )
    duration = _range_value(
        attributes.get("duration_min", ""),
        attributes.get("duration_max", ""),
    ) or _number(attributes.get("duration_seconds", ""))

    value = _range_value(
        attributes.get("damage_min", ""),
        attributes.get("damage_max", ""),
    )
    damage_value = bool(value)
    if not value:
        percent_range = _range_value(
            attributes.get("percent_min", ""),
            attributes.get("percent_max", ""),
        )
        if percent_range:
            value = f"{percent_range}%"
    if not value:
        for key in (
            "damage_percent",
            "percent",
            "reduction_percent",
        ):
            if key in attributes and (number := _number(attributes[key])):
                value = f"{number}%"
                break
    if not value:
        for key in ("flat", "value", "reduction_flat", "damage_min"):
            if key in attributes and (number := _number(attributes[key])):
                value = number
                damage_value = key == "damage_min"
                break
    if not value and "seconds" in attributes:
        seconds = _number(attributes["seconds"])
        value = f"{seconds}s" if seconds else ""

    if chance:
        value = f"{chance} chance" + (f" · {value}" if value else "")
    if duration:
        suffix = f"over {duration}s" if damage_value else f"for {duration}s"
        value = f"{value} {suffix}" if value else suffix
    if duration_percent := _percent(attributes.get("duration_percent", "")):
        value = f"{value} · +{duration_percent} duration" if value else (
            f"+{duration_percent} duration"
        )
    return value


def stat_table_html(
    rows: tuple[DetailStatRow, ...],
    *,
    color_for: Callable[[str, bool], str],
) -> str:
    """Render rows as conservative HTML supported by Qt's rich-text engine."""

    relevant = sorted(
        (row for row in rows if row.weight),
        key=lambda row: -row.weight,
    )
    other = [row for row in rows if not row.weight]
    groups = (("Relevant Stats", relevant), ("Other Stats", other))
    body: list[str] = []
    for heading, group in groups:
        if not group:
            continue
        body.append(
            '<tr><td colspan="3" bgcolor="#252b35" '
            'style="color:#e7ebf2; font-weight:600; padding:5px">'
            f"{escape(heading)}</td></tr>"
        )
        for row in group:
            matched = row.weight > 0
            color = color_for(row.stat_id, matched)
            body.append(
                "<tr>"
                f'<td style="color:{color}; white-space:nowrap; padding:4px 6px">'
                f"{escape(row.label)}</td>"
                f'<td align="right" style="color:{color}; white-space:nowrap; '
                'padding:4px 10px">'
                f"{escape(row.value)}</td>"
                '<td align="center" style="white-space:nowrap; padding:4px 6px">'
                f"{weight_stars_html(row.weight)}</td>"
                "</tr>"
            )
    if not body:
        body.append(
            '<tr><td colspan="3" style="color:#b7bec9; padding:5px">'
            "None</td></tr>"
        )
    return (
        '<table align="left" cellspacing="0" cellpadding="0" border="0" '
        'bgcolor="#171a1f">'
        '<tr bgcolor="#20252d">'
        '<th align="left" style="color:#b7bec9; padding:5px 6px">Stat</th>'
        '<th align="right" style="color:#b7bec9; padding:5px 10px">Value</th>'
        '<th align="center" style="color:#b7bec9; padding:5px 6px">Weight</th>'
        "</tr>"
        + "".join(body)
        + "</table>"
    )


def weight_stars_html(weight: int) -> str:
    weight = max(0, min(4, weight))
    return (
        '<span style="color:#f0b43c">'
        + ("★" * weight)
        + "</span>"
        + '<span style="color:#667080">'
        + ("☆" * (4 - weight))
        + "</span>"
    )


def _damage_type(raw: object) -> str:
    value = str(raw).strip().replace("_", " ")
    return value.title() if value else ""


def _signed(raw: object) -> str:
    value = _number(raw)
    if not value:
        return ""
    return value if value.startswith("-") else f"+{value}"


def _percent(raw: object) -> str:
    value = _number(raw)
    return f"{value}%" if value else ""


def _first_percent(attributes: dict[str, object], *keys: str) -> str:
    for key in keys:
        if key in attributes and (value := _percent(attributes[key])):
            return value
    return ""


def _range_value(minimum: object, maximum: object) -> str:
    low = _number(minimum)
    high = _number(maximum)
    if low and high and low != high:
        return f"{low}–{high}"
    return low or high


def _number(raw: object) -> str:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return ""
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
