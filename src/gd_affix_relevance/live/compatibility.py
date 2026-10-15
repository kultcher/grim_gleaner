"""Which Game.dll exports gg_hook needs. Mirrors native/gg_hook/src/game_types.h."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.live.pe_exports import is_64_bit, read_export_names

# Each requirement is satisfied by any one of its candidate symbols.
REQUIRED_EXPORTS: dict[str, tuple[str, ...]] = {
    "ItemEquipment::GetUIDisplayText": (
        "?GetUIDisplayText@ItemEquipment@GAME@@UEBAXPEBVCharacter@2@AEAV?$vector@UGameTextLine@GAME@@@mem@@_N@Z",
        "?GetUIDisplayText@ItemEquipment@GAME@@UEBAXPEBVCharacter@2@AEAV?$vector@UGameTextLine@GAME@@@mem@@@Z",
    ),
    "Item::GetItemReplicaInfo": (
        "?GetItemReplicaInfo@Item@GAME@@UEBAXAEAUItemReplicaInfo@2@@Z",
    ),
}


# Nice to have: their absence disables one feature, not the hook.
OPTIONAL_EXPORTS: dict[str, tuple[str, ...]] = {
    "Item::PassLootFilter (loot filter)": (
        "?PassLootFilter@Item@GAME@@QEBA_NW4ItemIgnore@InGameUIActorCapture@2@@Z",
    ),
}


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    game_dll: Path
    matched: dict[str, str]
    missing: tuple[str, ...]
    is_64_bit: bool = True
    optional_missing: tuple[str, ...] = ()

    @property
    def compatible(self) -> bool:
        return self.is_64_bit and not self.missing


def check_game_dll(game_dll: Path) -> CompatibilityReport:
    exports = read_export_names(game_dll)
    matched: dict[str, str] = {}
    missing: list[str] = []
    for requirement, candidates in REQUIRED_EXPORTS.items():
        found = next((name for name in candidates if name in exports), None)
        if found is None:
            missing.append(requirement)
        else:
            matched[requirement] = found
    optional_missing: list[str] = []
    for feature, candidates in OPTIONAL_EXPORTS.items():
        found = next((name for name in candidates if name in exports), None)
        if found is None:
            optional_missing.append(feature)
        else:
            matched[feature] = found
    return CompatibilityReport(
        Path(game_dll),
        matched,
        tuple(missing),
        is_64_bit(game_dll),
        tuple(optional_missing),
    )


def find_game_dll(game_folder: Path) -> Path:
    """Locate the 64-bit Game.dll.

    A Steam install keeps the 32-bit game in its root folder and the 64-bit
    game in ``x64``. The running game's own folder (already ``x64``) also works.
    """

    folder = Path(game_folder)
    for candidate in (folder / "x64" / "Game.dll", folder / "Game.dll"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Game.dll not found in {game_folder}")
