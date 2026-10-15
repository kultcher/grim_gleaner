#pragma once
// Guarded access to game objects: item records/seed, tooltip line lists,
// the detailed (roll range) tooltip pass and the injected label line.
//
// Every read is wrapped in structured exception handling (MSVC) and checked
// against the layouts confirmed in testing; on any mismatch the caller is
// told to stop rather than trust the data.

#include <cstdint>
#include <string>
#include <vector>

#include "stat_core.h"

namespace gg::game_access {

// Resolve Game.dll exports used here. Returns false (with *detail) if any is
// missing.
bool Initialize(std::string* detail);

struct ItemSnapshot {
    unsigned int seed = 0;
    std::string baseRecord;
    std::string prefixRecord;
    std::string suffixRecord;
    std::string modifierRecord;
    std::string materiaRecord;
    std::string relicBonus;
    std::string enchantmentRecord;
    std::string transmuteRecord;
    std::string ascendant1;
    std::string ascendant2;
};

enum class ReadResult { Ok, Fault, LayoutChanged };

// Item::GetItemReplicaInfo into a guard-padded buffer.
ReadResult ReadItem(const void* item, ItemSnapshot* out);

enum class LinesVerdict { Ok, BadSize, BadClass, TooLong, Fault };
const char* VerdictName(LinesVerdict verdict);

// Copy a mem::vector<GameTextLine> into UTF-8 lines.
LinesVerdict ReadLines(const void* lines, std::vector<core::TooltipLine>* out);

// Log the raw layout of a rejected vector once (for diagnosing patches).
void LogLinesDiagnostic(const void* lines, LinesVerdict verdict);

// Ask the game for the detailed (Ctrl) version of an item's tooltip into a
// private scratch list and read it. `build` is the original (unhooked)
// GetUIDisplayText. Returns false if the pass is unavailable or faulted.
using BuildTooltipFn = void (*)(const void* self, const void* character, void* lines,
                                bool detailed);
enum class DetailResult { Ok, Skipped, Failed };
DetailResult ReadDetailedLines(BuildTooltipFn build, const void* item, const void* character,
                               std::vector<core::TooltipLine>* out);

// Append one short line to the game's tooltip list, only if the list already
// has spare capacity and the text fits std::wstring's inline buffer (7 wide
// characters), so nothing is ever allocated or reallocated.
bool AppendShortLine(void* lines, int textClass, const std::string& asciiText);

}  // namespace gg::game_access
