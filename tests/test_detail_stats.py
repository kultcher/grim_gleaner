from gd_affix_relevance.catalog import AffixProperty
from gd_affix_relevance.ui.detail_stats import (
    build_detail_stat_rows,
    format_nominal_value,
    stat_table_html,
)


def _property(property_id: str, **attributes: str) -> AffixProperty:
    return AffixProperty(property_id, property_id, attributes)


def test_nominal_values_format_common_and_compound_property_shapes() -> None:
    assert format_nominal_value(
        _property("lightning_damage_percent", damage_percent="71.000000")
    ) == "71%"
    assert format_nominal_value(
        _property(
            "chance_flat_electrocute_damage",
            chance_percent="10",
            damage_min="90",
            duration_min="3",
        )
    ) == "10% chance · 90 over 3s"
    assert format_nominal_value(
        _property(
            "damage_conversion",
            percent="25",
            source_damage_type="Physical",
            destination_damage_type="Lightning",
        )
    ) == "25% from Physical"
    assert format_nominal_value(
        _property("skill_bonus", skill_level="2")
    ) == "+2"


def test_detail_rows_preserve_semantics_and_use_four_star_weights() -> None:
    properties = (
        _property("health", flat="125"),
        _property(
            "damage_conversion",
            percent="20",
            source_damage_type="Physical",
            destination_damage_type="Lightning",
        ),
        _property(
            "damage_conversion",
            percent="30",
            source_damage_type="Cold",
            destination_damage_type="Lightning",
        ),
    )
    rows = build_detail_stat_rows(
        (
            "health",
            "damage_conversion_to_lightning",
            "base_weapon_damage_as_physical",
        ),
        properties,
        label_for=lambda stat_id: stat_id,
        weight_for=lambda stat_id: 4 if stat_id == "health" else 0,
    )

    assert [(row.stat_id, row.value, row.weight) for row in rows] == [
        ("health", "125", 4),
        (
            "damage_conversion_to_lightning",
            "20% from Physical; 30% from Cold",
            0,
        ),
        ("base_weapon_damage_as_physical", "Implicit", 0),
    ]
    rendered = stat_table_html(rows, color_for=lambda _stat, _matched: "#fff")
    assert "Relevant Stats" in rendered
    assert "Other Stats" in rendered
    assert "★★★★" in rendered
    assert "☆☆☆☆" in rendered
    assert '<table align="left"' in rendered
    assert 'width="100%"' not in rendered
    assert "white-space:nowrap" in rendered
