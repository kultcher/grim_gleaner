#include "game_access.h"

#include <windows.h>

#include <cstdio>
#include <cstring>
#include <mutex>
#include <new>

#include "game_types.h"
#include "hook_log.h"

namespace gg::game_access {
namespace {

using game::GameTextLine;
using game::GameTextLineVector;
using game::ItemReplicaInfo;

using GetItemReplicaInfoFn = void (*)(const void* self, ItemReplicaInfo* out);
GetItemReplicaInfoFn g_getReplica = nullptr;

constexpr std::size_t kGuardBytes = 0x100;
constexpr unsigned char kGuardFill = 0xA5;
constexpr std::size_t kMaxLines = 128;
constexpr std::size_t kInlineWideChars = 7;  // MSVC std::wstring SSO capacity

struct RawLine {
    int textClass;
    const wchar_t* text;
    std::size_t length;
};

bool CallGetReplicaGuarded(const void* item, ItemReplicaInfo* out) {
    // No objects with destructors here: SEH cannot unwind them.
#if defined(_MSC_VER)
    __try {
        g_getReplica(item, out);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
#else
    g_getReplica(item, out);
    return true;
#endif
}

LinesVerdict SnapshotLinesGuarded(const void* lines, RawLine* out, int* count) {
#if defined(_MSC_VER)
    __try {
#endif
        *count = 0;
        const auto* vector = static_cast<const GameTextLineVector*>(lines);
        if (vector->first == nullptr) {
            return LinesVerdict::Ok;
        }
        const auto bytes = reinterpret_cast<const char*>(vector->last) -
                           reinterpret_cast<const char*>(vector->first);
        if (bytes < 0 || bytes % sizeof(GameTextLine) != 0 || vector->end < vector->last) {
            return LinesVerdict::BadSize;
        }
        std::size_t total = static_cast<std::size_t>(bytes) / sizeof(GameTextLine);
        if (total > kMaxLines) {
            total = kMaxLines;
        }
        for (std::size_t index = 0; index < total; ++index) {
            const GameTextLine& line = vector->first[index];
            if (line.textClass < 0 || line.textClass > game::kMaxGameTextClass) {
                return LinesVerdict::BadClass;
            }
            if (line.text.size() > 4096) {
                return LinesVerdict::TooLong;
            }
            out[index] = RawLine{line.textClass, line.text.data(), line.text.size()};
        }
        *count = static_cast<int>(total);
        return LinesVerdict::Ok;
#if defined(_MSC_VER)
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return LinesVerdict::Fault;
    }
#endif
}

bool SafeCopy(void* destination, const void* source, std::size_t size) {
#if defined(_MSC_VER)
    __try {
        std::memcpy(destination, source, size);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
#else
    std::memcpy(destination, source, size);
    return true;
#endif
}

std::string ToUtf8(const wchar_t* text, std::size_t length) {
    if (length == 0) {
        return {};
    }
    const int size = WideCharToMultiByte(CP_UTF8, 0, text, static_cast<int>(length),
                                         nullptr, 0, nullptr, nullptr);
    if (size <= 0) {
        return {};
    }
    std::string result(static_cast<std::size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, text, static_cast<int>(length), result.data(), size,
                        nullptr, nullptr);
    return result;
}

std::string Hex(const unsigned char* data, std::size_t size) {
    static const char digits[] = "0123456789abcdef";
    std::string result;
    for (std::size_t index = 0; index < size; ++index) {
        if (index % 16 == 0) {
            char offset[16];
            std::snprintf(offset, sizeof(offset), "\n  +%03zx ", index);
            result += offset;
        }
        result += digits[data[index] >> 4];
        result += digits[data[index] & 0xF];
        result += ' ';
    }
    return result;
}

// The detailed pass writes into this list. Its storage is allocated by the
// game on first use and then reused; elements are destroyed after each read.
GameTextLineVector g_scratch{nullptr, nullptr, nullptr};
std::mutex g_scratchMutex;

bool CallBuildGuarded(BuildTooltipFn build, const void* item, const void* character,
                      void* lines) {
#if defined(_MSC_VER)
    __try {
        build(item, character, lines, true);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
#else
    build(item, character, lines, true);
    return true;
#endif
}

void ClearScratch() {
    for (GameTextLine* line = g_scratch.first; line != nullptr && line < g_scratch.last; ++line) {
        line->~GameTextLine();
    }
    g_scratch.last = g_scratch.first;
}

}  // namespace

bool Initialize(std::string* detail) {
    HMODULE gameDll = GetModuleHandleW(L"Game.dll");
    if (gameDll == nullptr) {
        *detail = "Game.dll is not loaded";
        return false;
    }
    g_getReplica = reinterpret_cast<GetItemReplicaInfoFn>(
        GetProcAddress(gameDll, game::kItemGetItemReplicaInfo));
    if (g_getReplica == nullptr) {
        *detail = "Game.dll has no Item::GetItemReplicaInfo export";
        return false;
    }
    return true;
}

ReadResult ReadItem(const void* item, ItemSnapshot* out) {
    alignas(ItemReplicaInfo) unsigned char storage[sizeof(ItemReplicaInfo) + kGuardBytes];
    std::memset(storage + sizeof(ItemReplicaInfo), kGuardFill, kGuardBytes);
    auto* info = new (storage) ItemReplicaInfo();
    const bool ok = CallGetReplicaGuarded(item, info);
    for (std::size_t index = 0; index < kGuardBytes; ++index) {
        if (storage[sizeof(ItemReplicaInfo) + index] != kGuardFill) {
            return ReadResult::LayoutChanged;  // leak rather than free garbage
        }
    }
    if (!ok) {
        return ReadResult::Fault;
    }
    out->seed = info->seed;
    out->baseRecord = info->baseRecord;
    out->prefixRecord = info->prefixRecord;
    out->suffixRecord = info->suffixRecord;
    out->modifierRecord = info->modifierRecord;
    out->materiaRecord = info->materiaRecord;
    out->relicBonus = info->relicBonus;
    out->enchantmentRecord = info->enchantmentRecord;
    out->transmuteRecord = info->transmuteRecord;
    out->ascendant1 = info->ascendant1;
    out->ascendant2 = info->ascendant2;
    info->~ItemReplicaInfo();
    return ReadResult::Ok;
}

const char* VerdictName(LinesVerdict verdict) {
    switch (verdict) {
        case LinesVerdict::Ok: return "ok";
        case LinesVerdict::BadSize: return "byte span is not a whole number of GameTextLine";
        case LinesVerdict::BadClass: return "text class outside 0..255";
        case LinesVerdict::TooLong: return "string length implausible";
        case LinesVerdict::Fault: return "access violation while reading";
    }
    return "?";
}

LinesVerdict ReadLines(const void* lines, std::vector<core::TooltipLine>* out) {
    out->clear();
    if (lines == nullptr) {
        return LinesVerdict::Ok;
    }
    RawLine raw[kMaxLines];
    int count = 0;
    const LinesVerdict verdict = SnapshotLinesGuarded(lines, raw, &count);
    if (verdict != LinesVerdict::Ok) {
        return verdict;
    }
    out->reserve(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index) {
        out->push_back({raw[index].textClass, ToUtf8(raw[index].text, raw[index].length)});
    }
    return LinesVerdict::Ok;
}

void LogLinesDiagnostic(const void* lines, LinesVerdict verdict) {
    std::string report = std::string("tooltip lines rejected: ") + VerdictName(verdict) +
                         "; expected sizeof(GameTextLine)=" +
                         std::to_string(sizeof(GameTextLine));
    unsigned char header[48] = {};
    if (!SafeCopy(header, lines, sizeof(header))) {
        Log(report + "; vector header unreadable");
        return;
    }
    report += "\nvector header (48 bytes):" + Hex(header, sizeof(header));
    const void* first = nullptr;
    std::memcpy(&first, header, sizeof(first));
    unsigned char element[0x100] = {};
    if (first != nullptr && SafeCopy(element, first, sizeof(element))) {
        report += "\nfirst 0x100 bytes at first pointer:" + Hex(element, sizeof(element));
    } else {
        report += "\nfirst pointer unreadable";
    }
    Log(report);
}

DetailResult ReadDetailedLines(BuildTooltipFn build, const void* item,
                               const void* character,
                               std::vector<core::TooltipLine>* out) {
    std::unique_lock<std::mutex> lock(g_scratchMutex, std::try_to_lock);
    if (!lock.owns_lock() || build == nullptr) {
        return DetailResult::Skipped;
    }
    ClearScratch();
    if (!CallBuildGuarded(build, item, character, &g_scratch)) {
        // The list may be half-built; abandon it (leak) rather than touch it.
        g_scratch = GameTextLineVector{nullptr, nullptr, nullptr};
        return DetailResult::Failed;
    }
    const LinesVerdict verdict = ReadLines(&g_scratch, out);
    ClearScratch();
    return verdict == LinesVerdict::Ok ? DetailResult::Ok : DetailResult::Failed;
}

bool AppendShortLine(void* lines, int textClass, const std::string& asciiText) {
    if (lines == nullptr || asciiText.empty() || asciiText.size() > kInlineWideChars) {
        return false;
    }
    auto* vector = static_cast<GameTextLineVector*>(lines);
    if (vector->first == nullptr || vector->last == nullptr || vector->end == nullptr ||
        vector->last >= vector->end) {
        return false;  // no spare capacity: never grow the game's list
    }
    std::wstring text(asciiText.begin(), asciiText.end());  // inline, no heap
    new (vector->last) GameTextLine{textClass, std::move(text), false, nullptr, 1.0f};
    ++vector->last;
    return true;
}

}  // namespace gg::game_access
