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
    profile = BuildProfile("Bleed", {"health": 2, "bleeding_damage_percent": 4})

    restored = BuildProfile.from_dict(profile.to_dict())

    assert restored.name == profile.name
    assert restored.weights == profile.weights
    assert list(profile.to_dict()["weights"]) == [
        "bleeding_damage_percent",
        "health",
    ]
