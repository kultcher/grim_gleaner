from __future__ import annotations

import pytest

from gd_affix_relevance.catalog.models import (
    MagnitudeCatalog,
    MagnitudeEntry,
    MagnitudeProperty,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import score_semantic_stat_ids
from gd_affix_relevance.scoring.magnitude import (
    MIN_COHORT,
    MagnitudeModel,
    profile_multipliers,
    set_active_magnitude_model,
)


def _entry(record: str, value: float, *, stat: str = "fire_damage_percent",
           entity_type: str = "item", cohort: str = "c1") -> MagnitudeEntry:
    return MagnitudeEntry(
        entity_type=entity_type,
        entity_id=f"equipment:{record}",
        variant_id=f"base:{record}",
        band_id="90+",
        gear_slot="Ring",
        category="epic",
        rarity="Epic",
        level_requirement=94,
        band_variant_ids=(f"base:{record}",),
        properties=(
            MagnitudeProperty(
                property_id=stat,
                property_key=stat,
                scalar_value=value,
                value_roles=("damage_percent",),
                percentile=0.0,
                cohort_size=0,
                cohort_id=cohort,
            ),
        ),
    )


def _model(values: list[float], scales: dict[str, float] | None = None) -> MagnitudeModel:
    entries = tuple(_entry(f"r{index}.dbr", value) for index, value in enumerate(values))
    return MagnitudeModel(MagnitudeCatalog((), entries), scales)


def test_midrank_percentiles_and_multipliers() -> None:
    model = _model([10, 20, 30, 40, 50])
    assert model.stats("r0.dbr", "90+")["fire_damage_percent"].percentile == 0.0
    assert model.stats("R4.DBR", "90+")["fire_damage_percent"].percentile == 1.0
    multipliers = model.multipliers(["r4.dbr"], "90+", 0.10)
    assert multipliers == {"fire_damage_percent": pytest.approx(1.10)}
    assert model.multipliers(["r0.dbr"], "90+", 0.10)["fire_damage_percent"] == pytest.approx(0.90)
    assert model.multipliers(["r2.dbr"], "90+", 0.10)["fire_damage_percent"] == pytest.approx(1.0)


def test_small_cohorts_are_neutral() -> None:
    model = _model([10, 20, 30][: MIN_COHORT - 1])
    assert model.multipliers(["r2.dbr"], "90+", 0.2) == {}


def test_named_item_scale_is_applied_before_ranking() -> None:
    # r0 has the lowest raw value but a 300% scale lifts it to the top.
    model = _model([10, 20, 30, 35], scales={"records/r0.dbr": 0.0, "r0.dbr": 300.0})
    assert model.stats("r0.dbr", "90+")["fire_damage_percent"].percentile == 1.0


def test_off_reproduces_plain_scores_exactly() -> None:
    profile = BuildProfile(weights={"fire_damage_percent": 4, "health": 2})
    set_active_magnitude_model(_model([10, 20, 30, 40, 50]))
    try:
        assert profile_multipliers(profile, ["r4.dbr"]) is None
        profile.set_magnitude_influence("normal")
        multipliers = profile_multipliers(profile, ["r4.dbr"])
        stats = ("fire_damage_percent", "health")
        plain = score_semantic_stat_ids(stats, profile)
        boosted = score_semantic_stat_ids(stats, profile, multipliers=multipliers)
        assert boosted.relevance_points == pytest.approx(4.0 * 1.1 + 1.0)
        assert plain.relevance_points == pytest.approx(5.0)
        assert score_semantic_stat_ids(stats, profile, multipliers={}) == plain
    finally:
        set_active_magnitude_model(None)


def test_profile_rejects_unknown_influence() -> None:
    with pytest.raises(ValueError):
        BuildProfile(magnitude_influence="extreme")
    restored = BuildProfile.from_dict(BuildProfile(magnitude_influence="high").to_dict())
    assert restored.magnitude_influence == "high"


def test_profile_levels_match_scoring_levels() -> None:
    from gd_affix_relevance.domain.profile import MAGNITUDE_INFLUENCE_LEVELS
    from gd_affix_relevance.scoring.magnitude import MAGNITUDE_INFLUENCE

    assert tuple(MAGNITUDE_INFLUENCE) == MAGNITUDE_INFLUENCE_LEVELS
