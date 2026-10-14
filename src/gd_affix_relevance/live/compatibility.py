"""Which Game.dll exports gg_hook needs. Mirrors native/gg_hook/src/game_types.h."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.live.pe_exports import read_export_names

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


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    game_dll: Path
    matched: dict[str, str]
    missing: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return not self.missing


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
    return CompatibilityReport(Path(game_dll), matched, tuple(missing))


def find_game_dll(game_folder: Path) -> Path:
    for candidate in (Path(game_folder) / "Game.dll", Path(game_folder) / "x64" / "Game.dll"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Game.dll not found in {game_folder}")
