#pragma once
#include <cstdint>
#include <string>

namespace gg {
// Hooks ItemEquipment::GetUIDisplayText in Game.dll. On failure returns false
// and leaves the game untouched; *detail explains why either way.
bool InstallTooltipHook(std::string* detail);

// Number of tooltip builds seen so far (for heartbeats and diagnostics).
std::uint64_t TooltipCallCount();
}  // namespace gg
