import pytest

from gd_affix_relevance.domain import BuildProfile


def test_profile_validates_and_removes_zero_weights() -> None:
    profile = BuildProfile("Test")
    profile.set_weight("health", 4)
    assert profile.weight_for("health") == 4

    profile.set_weight("health", 0)
    assert profile.weight_for("health") == 0
    assert "health" not in profile.weights

    with pytest.raises(ValueError):
        profile.set_weight("health", 5)
    with pytest.raises(TypeError):
        profile.set_weight("health", True)
    with pytest.raises(ValueError):
        BuildProfile("Invalid", {"health": 5})


def test_profile_round_trip_is_deterministic() -> None:
    profile = BuildProfile(
        "Bleed",
        {"health": 2, "bleeding_damage_percent": 4},
        ("playerclass06", "playerclass04"),
        {"records/skills/playerclass06/savagery1.dbr": 4},
    )

    restored = BuildProfile.from_dict(profile.to_dict())

    assert restored.name == profile.name
    assert restored.weights == profile.weights
    assert restored.masteries == profile.masteries
    assert restored.skill_weights == profile.skill_weights
    assert list(profile.to_dict()["weights"]) == [
        "bleeding_damage_percent",
        "health",
    ]


def test_conversion_sources_default_enabled_and_round_trip_exclusions() -> None:
    profile = BuildProfile(weights={"damage_conversion_to_fire": 4})

    assert profile.conversion_source_enabled("fire", "physical")
    profile.set_conversion_source_enabled("fire", "physical", False)
    profile.set_conversion_source_enabled("fire", "chaos", False)
    assert not profile.conversion_source_enabled("Fire", "Physical")

    restored = BuildProfile.from_dict(profile.to_dict())
    assert restored.excluded_conversion_sources == {
        "fire": {"chaos", "physical"}
    }
    restored.set_conversion_source_enabled("fire", "physical", True)
    assert restored.conversion_source_enabled("fire", "physical")

    restored.set_conversion_source_enabled("fire", "specific skill", False)
    assert not restored.conversion_source_enabled("fire", "specific_skill")
    assert BuildProfile.from_dict(restored.to_dict()).excluded_conversion_sources == {
        "fire": {"chaos", "specific_skill"}
    }

    with pytest.raises(ValueError, match="must differ"):
        profile.set_conversion_source_enabled("fire", "fire", False)


def test_profile_masteries_are_exclusive_and_zero_weight_skills_persist() -> None:
    profile = BuildProfile()
    profile.set_mastery(0, "playerclass01")
    profile.set_mastery(1, "playerclass02")
    profile.set_skill_weight("records/skills/playerclass01/cadence1.dbr", 0)

    assert profile.masteries == ("playerclass01", "playerclass02")
    assert profile.skill_weights == {
        "records/skills/playerclass01/cadence1.dbr": 0
    }
    with pytest.raises(ValueError, match="same mastery"):
        profile.set_mastery(1, "playerclass01")
