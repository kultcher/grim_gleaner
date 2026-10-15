#pragma once
#include <string>

namespace gg {
// Hooks Item::PassLootFilter so items graded below the active profile's
// per-rarity threshold fail the game's own loot filter. Optional: failure to
// install leaves everything else working.
bool InstallLootFilterHook(std::string* detail);
}  // namespace gg
