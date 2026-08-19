"""Shared level-band definitions for profiles, catalogs, and UI controls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LevelBandDefinition:
    band_id: str
    minimum_level: int
    maximum_level: int | None

    @property
    def display_label(self) -> str:
        return f"Levels {self.band_id}"


LEVEL_BANDS = (
    LevelBandDefinition("1-49", 1, 49),
    LevelBandDefinition("50-64", 50, 64),
    LevelBandDefinition("65-79", 65, 79),
    LevelBandDefinition("80-89", 80, 89),
    LevelBandDefinition("90+", 90, None),
)
LEVEL_BAND_IDS = tuple(band.band_id for band in LEVEL_BANDS)
DEFAULT_LEVEL_BAND_ID = "90+"


def validate_level_band_id(band_id: str) -> str:
    if not isinstance(band_id, str):
        raise TypeError("profile level band must be a string")
    normalized = band_id.strip()
    if normalized not in LEVEL_BAND_IDS:
        raise ValueError(f"unknown profile level band: {band_id!r}")
    return normalized


def level_band_definition(band_id: str) -> LevelBandDefinition:
    """Return the validated definition for a persisted profile band."""

    normalized = validate_level_band_id(band_id)
    return next(band for band in LEVEL_BANDS if band.band_id == normalized)


def level_is_eligible(level_requirement: int, band_id: str) -> bool:
    """Whether a concrete record can be equipped within the selected band.

    Grim Dawn records commonly use zero for an unrestricted/starting-level
    entry. Treat that as level one, matching the catalog magnitude builder.
    """

    maximum = level_band_definition(band_id).maximum_level
    effective_level = max(1, int(level_requirement))
    return maximum is None or effective_level <= maximum
