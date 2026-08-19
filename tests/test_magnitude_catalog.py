from gd_affix_relevance.catalog.magnitude import compile_magnitude_payload


def _property(
    property_id: str,
    value: str,
    *,
    role: str = "percent",
    key: str | None = None,
    **qualifiers: str,
) -> dict[str, object]:
    return {
        "property_id": property_id,
        "property_key": key or property_id,
        "attributes": {role: value, **qualifiers},
    }


def _tier(
    tier_id: str,
    level: int,
    properties: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "tier_id": tier_id,
        "source": "base",
        "record_path": tier_id.removeprefix("base:"),
        "gear_slot": "Ring",
        "applicable_slots": ["ring"],
        "level_requirement": level,
        "properties": properties,
        "stat_lines": [],
    }


def test_magnitude_index_selects_band_tiers_and_computes_percentiles() -> None:
    affixes = [
        {
            "affix_id": "prefix:low",
            "kind": "prefix",
            "rarity": "Rare",
            "tiers": [
                _tier(
                    "base:records/low_10.dbr",
                    10,
                    [_property("lightning_damage_percent", "10")],
                ),
                _tier(
                    "base:records/low_40.dbr",
                    40,
                    [
                        _property("lightning_damage_percent", "20"),
                        _property("offensive_ability", "15", role="flat"),
                    ],
                ),
            ],
        },
        {
            "affix_id": "prefix:high",
            "kind": "prefix",
            "rarity": "Rare",
            "tiers": [
                _tier(
                    "base:records/high_40.dbr",
                    40,
                    [_property("lightning_damage_percent", "40")],
                )
            ],
        },
    ]

    payload = compile_magnitude_payload(affixes, {})
    entries = {
        (entry["entity_id"], entry["band_id"]): entry
        for entry in payload["entries"]
    }
    low = entries[("prefix:low", "1-49")]
    high = entries[("prefix:high", "1-49")]
    assert low["level_requirement"] == 40
    assert low["band_variant_ids"] == [
        "base:records/low_10.dbr",
        "base:records/low_40.dbr",
    ]
    low_lightning = next(
        property_
        for property_ in low["properties"]
        if property_["property_id"] == "lightning_damage_percent"
    )
    high_lightning = next(
        property_
        for property_ in high["properties"]
        if property_["property_id"] == "lightning_damage_percent"
    )
    assert low_lightning["scalar_value"] == 20.0
    assert low_lightning["percentile"] == 0.0
    assert high_lightning["percentile"] == 1.0
    assert low_lightning["cohort_size"] == 2


def test_magnitude_index_uses_skill_rank_and_ignores_compound_effects() -> None:
    affixes = [
        {
            "affix_id": "prefix:skilled",
            "kind": "prefix",
            "rarity": "Rare",
            "tiers": [
                _tier(
                    "base:records/skilled.dbr",
                    20,
                    [
                        _property(
                            "skill_bonus",
                            "3",
                            role="skill_level",
                            skill_reference="records/skills/test.dbr",
                        ),
                        {
                            "property_id": "chance_flat_fire_damage",
                            "property_key": "chance_flat_fire_damage",
                            "attributes": {
                                "chance_percent": "10",
                                "damage_min": "5",
                                "damage_max": "9",
                            },
                        },
                    ],
                )
            ],
        }
    ]

    payload = compile_magnitude_payload(affixes, {})
    entry = next(
        entry
        for entry in payload["entries"]
        if entry["band_id"] == "1-49"
    )
    assert [item["property_id"] for item in entry["properties"]] == [
        "skill_bonus"
    ]
    assert entry["properties"][0]["scalar_value"] == 3.0
    assert entry["properties"][0]["percentile"] == 0.5
