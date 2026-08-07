"""Stable atomic equipment slots shared by catalogs, scoring, and UI."""

from __future__ import annotations

SLOT_WEAPON_1H_MELEE = "weapon_1h_melee"
SLOT_WEAPON_2H_MELEE = "weapon_2h_melee"
SLOT_WEAPON_1H_CASTER = "weapon_1h_caster"
SLOT_WEAPON_1H_RANGED = "weapon_1h_ranged"
SLOT_WEAPON_2H_RANGED = "weapon_2h_ranged"
SLOT_SHIELD = "shield"
SLOT_OFF_HAND = "off_hand"
SLOT_RING = "ring"
SLOT_AMULET = "amulet"
SLOT_MEDAL = "medal"
SLOT_WAIST = "waist"
SLOT_HEAD = "head"
SLOT_CHEST = "chest"
SLOT_SHOULDERS = "shoulders"
SLOT_LEGS = "legs"
SLOT_HANDS = "hands"
SLOT_FEET = "feet"

WEAPON_SLOTS = (
    SLOT_WEAPON_1H_MELEE,
    SLOT_WEAPON_2H_MELEE,
    SLOT_WEAPON_1H_CASTER,
    SLOT_WEAPON_1H_RANGED,
    SLOT_WEAPON_2H_RANGED,
)
ARMOR_SLOTS = (
    SLOT_HEAD,
    SLOT_SHOULDERS,
    SLOT_CHEST,
    SLOT_HANDS,
    SLOT_LEGS,
    SLOT_FEET,
)

SLOT_LABELS = {
    SLOT_WEAPON_1H_MELEE: "1H Melee",
    SLOT_WEAPON_2H_MELEE: "2H Melee",
    SLOT_WEAPON_1H_CASTER: "1H Caster",
    SLOT_WEAPON_1H_RANGED: "1H Ranged",
    SLOT_WEAPON_2H_RANGED: "2H Ranged",
    SLOT_SHIELD: "Shield",
    SLOT_OFF_HAND: "Off-hand",
    SLOT_RING: "Ring",
    SLOT_AMULET: "Amulet",
    SLOT_MEDAL: "Medal",
    SLOT_WAIST: "Belt",
    SLOT_HEAD: "Helm",
    SLOT_CHEST: "Chest",
    SLOT_SHOULDERS: "Shoulders",
    SLOT_LEGS: "Pants",
    SLOT_HANDS: "Gloves",
    SLOT_FEET: "Boots",
}

SLOT_GROUPS = (
    ("Weapons", WEAPON_SLOTS),
    ("Off-hands", (SLOT_SHIELD, SLOT_OFF_HAND)),
    ("Accessories", (SLOT_RING, SLOT_AMULET, SLOT_MEDAL, SLOT_WAIST)),
    ("Armor", (SLOT_HEAD, SLOT_CHEST, SLOT_SHOULDERS, SLOT_LEGS, SLOT_HANDS, SLOT_FEET)),
)

SLOT_FILTERS = {
    SLOT_WEAPON_1H_MELEE: frozenset({"one_handed", "melee"}),
    SLOT_WEAPON_2H_MELEE: frozenset({"two_handed", "melee"}),
    SLOT_WEAPON_1H_CASTER: frozenset({"one_handed", "caster"}),
    SLOT_WEAPON_1H_RANGED: frozenset({"one_handed", "ranged"}),
    SLOT_WEAPON_2H_RANGED: frozenset({"two_handed", "ranged"}),
    SLOT_SHIELD: frozenset({"shield"}),
    SLOT_OFF_HAND: frozenset({"off_hand"}),
}

FILTER_LABELS = (
    ("one_handed", "1H"),
    ("two_handed", "2H"),
    ("melee", "Melee"),
    ("caster", "Caster"),
    ("ranged", "Ranged"),
    ("shield", "Shield"),
    ("off_hand", "Off-hand"),
)


def slot_sort_key(slot_id: str) -> tuple[int, str]:
    ordered = tuple(slot for _, slots in SLOT_GROUPS for slot in slots)
    try:
        return ordered.index(slot_id), slot_id
    except ValueError:
        return len(ordered), slot_id


def slot_ids_from_legacy_label(label: str) -> tuple[str, ...]:
    """Best-effort compatibility for hand-built or older affix variants."""

    aliases = {
        "All armor": ARMOR_SLOTS,
        "Ring": (SLOT_RING,),
        "Rings, Amulets": (SLOT_RING, SLOT_AMULET),
        "Amulet": (SLOT_AMULET,),
        "Medal": (SLOT_MEDAL,),
        "Waist": (SLOT_WAIST,),
        "Head": (SLOT_HEAD,),
        "Shoulders": (SLOT_SHOULDERS,),
        "Chest": (SLOT_CHEST,),
        "Hands": (SLOT_HANDS,),
        "Legs": (SLOT_LEGS,),
        "Feet": (SLOT_FEET,),
        "Shields": (SLOT_SHIELD,),
        "Off-hands": (SLOT_OFF_HAND,),
        "One-handed weapons": (
            SLOT_WEAPON_1H_MELEE,
            SLOT_WEAPON_1H_CASTER,
            SLOT_WEAPON_1H_RANGED,
        ),
        "Two-handed weapons": (
            SLOT_WEAPON_2H_MELEE,
            SLOT_WEAPON_2H_RANGED,
        ),
        "All weapons": WEAPON_SLOTS,
    }
    slots: list[str] = []
    for part in label.split("; "):
        slots.extend(aliases.get(part, ()))
    return tuple(dict.fromkeys(slots))


def equipment_class_slot_id(item_class: str) -> str:
    """Map a concrete equipment DBR class onto an atomic recommendation slot."""

    fixed = {
        "ArmorProtective_Head": SLOT_HEAD,
        "ArmorProtective_Shoulders": SLOT_SHOULDERS,
        "ArmorProtective_Chest": SLOT_CHEST,
        "ArmorProtective_Hands": SLOT_HANDS,
        "ArmorProtective_Legs": SLOT_LEGS,
        "ArmorProtective_Feet": SLOT_FEET,
        "ArmorProtective_Waist": SLOT_WAIST,
        "ArmorJewelry_Ring": SLOT_RING,
        "ArmorJewelry_Amulet": SLOT_AMULET,
        "ArmorJewelry_Medal": SLOT_MEDAL,
        "WeaponArmor_Shield": SLOT_SHIELD,
        "WeaponArmor_Offhand": SLOT_OFF_HAND,
        "WeaponMelee_Dagger": SLOT_WEAPON_1H_CASTER,
        "WeaponMelee_Scepter": SLOT_WEAPON_1H_CASTER,
        "WeaponHunting_Ranged1h": SLOT_WEAPON_1H_RANGED,
        "WeaponHunting_Ranged2h": SLOT_WEAPON_2H_RANGED,
    }
    if item_class in fixed:
        return fixed[item_class]
    if item_class.startswith("WeaponMelee_"):
        return (
            SLOT_WEAPON_2H_MELEE
            if item_class.endswith("2h")
            else SLOT_WEAPON_1H_MELEE
        )
    return ""
