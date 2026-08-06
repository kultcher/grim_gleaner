import json
from pathlib import Path

import pytest

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import (
    PROFILE_FILE_SCHEMA_VERSION,
    ProfileFormatError,
    load_profile,
    save_profile,
)


def test_profile_file_round_trip_is_versioned_and_deterministic(
    tmp_path: Path,
) -> None:
    profile = BuildProfile(
        "Bleed Werewolf",
        {"health": 2, "bleeding_damage_percent": 4},
    )

    destination = save_profile(profile, tmp_path / "bleed-werewolf")
    first_bytes = destination.read_bytes()
    save_profile(profile, destination)

    assert destination.name == "bleed-werewolf.json"
    assert destination.read_bytes() == first_bytes
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": PROFILE_FILE_SCHEMA_VERSION,
        "masteries": ["", ""],
        "name": "Bleed Werewolf",
        "skill_weights": {},
        "weights": {
            "bleeding_damage_percent": 4,
            "health": 2,
        },
    }
    assert load_profile(destination).to_dict() == profile.to_dict()
    assert not destination.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    "payload, message",
    (
        ([], "JSON object"),
        ({"schema_version": 99, "name": "Future", "weights": {}}, "schema"),
        ({"schema_version": True, "name": "Boolean", "weights": {}}, "schema"),
        (
            {"schema_version": 1, "name": "Invalid", "weights": {"health": 5}},
            "weight",
        ),
    ),
)
def test_profile_file_rejects_invalid_data(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProfileFormatError, match=message):
        load_profile(source)


def test_profile_file_reports_malformed_json(tmp_path: Path) -> None:
    source = tmp_path / "broken.json"
    source.write_text("{ definitely not json", encoding="utf-8")

    with pytest.raises(ProfileFormatError, match="Could not read profile"):
        load_profile(source)


def test_profile_loader_migrates_schema_one_with_empty_skill_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "Legacy",
                "weights": {"health": 2},
            }
        ),
        encoding="utf-8",
    )

    profile = load_profile(source)

    assert profile.masteries == ("", "")
    assert profile.skill_weights == {}
    assert profile.weights == {"health": 2}
