"""Grim Dawn's ``attributeScalePercent`` rule for named items.

Epic, Legendary and Monster Infrequent records store authored values plus a
scale percentage. For confirmed offensive roles the displayed centre value is
``int(raw * (1 + scale / 100))``; everything else is shown as authored. See
docs/magnitude-backburner-reminder.md ("Named-item scaling findings").

Shared by the item detail pane and the magnitude model so the two cannot
drift apart.
"""

from __future__ import annotations

_NO_ROLES: frozenset[str] = frozenset()


def scaled_roles(property_id: str, property_key: str) -> frozenset[str]:
    """Attribute roles of a property that the named-item scale applies to."""

    if property_key.endswith(":base_weapon"):
        return _NO_ROLES
    if property_id in {"total_damage_percent", "stun_duration"}:
        return frozenset({"percent"})
    if (
        property_id.endswith("_damage_percent")
        and not property_id.startswith("pet_")
        and property_id not in {"retaliation_damage_percent", "weapon_damage_percent"}
    ):
        return frozenset({"damage_percent", "duration_percent"})
    if (
        property_id.startswith("flat_") or property_id.startswith("chance_flat_")
    ) and property_id.endswith("_damage"):
        return frozenset({"damage_min", "damage_max"})
    return _NO_ROLES


def scale_multiplier(scale_percent: float | None) -> float:
    return 1.0 + float(scale_percent or 0.0) / 100.0


def scale_attributes(
    property_id: str,
    property_key: str,
    attributes: dict[str, str],
    scale_percent: float | None,
) -> dict[str, str]:
    """Apply the named-item scale to the confirmed roles of one property."""

    if not scale_percent:
        return attributes
    roles = scaled_roles(property_id, property_key)
    if not roles:
        return attributes
    scaled = dict(attributes)
    multiplier = scale_multiplier(scale_percent)
    for role in roles:
        if role not in scaled:
            continue
        try:
            raw_value = float(scaled[role])
        except (TypeError, ValueError):
            continue
        # The game truncates the scaled authored value before applying its
        # separate display-roll range.
        scaled[role] = str(int(raw_value * multiplier))
    return scaled
