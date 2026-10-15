#include "tooltip_hook.h"

#include <windows.h>
#include <tlhelp32.h>

#include <detours.h>

#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <new>
#include <vector>

#include "game_types.h"
#include "hook_log.h"
#include "reporter.h"

namespace gg {
namespace {

using game::GameTextLine;
using game::GameTextLineVector;
using game::ItemReplicaInfo;

// x64 has a single calling convention; `this` arrives first.
using GetUIDisplayText4Fn = void (*)(const void* self, const void* character,
                                     void* lines, bool includeSetBonusDetails);
using GetUIDisplayText3Fn = void (*)(const void* self, const void* character,
                                     void* lines);
using GetItemReplicaInfoFn = void (*)(const void* self, ItemReplicaInfo* out);

GetUIDisplayText4Fn g_original4 = nullptr;
GetUIDisplayText3Fn g_original3 = nullptr;
GetItemReplicaInfoFn g_getReplica = nullptr;

std::atomic<std::uint64_t> g_calls{0};
std::atomic<bool> g_reportingDisabled{false};
// Tooltip text is optional extra: if its layout looks wrong, keep reporting
// records and seeds but stop reading lines.
std::atomic<bool> g_linesDisabled{false};
constexpr std::size_t kMaxLines = 128;

struct RawLine {
    int textClass;
    const wchar_t* text;
    std::size_t length;
};

// The same tooltip is rebuilt repeatedly while it is shown. Report an item
// once, then again only after it has gone unreported for a while.
constexpr ULONGLONG kRepeatAfterMs = 2000;
std::mutex g_dedupeMutex;
const void* g_lastItem = nullptr;
ULONGLONG g_lastReportTick = 0;

// Room for the game to write past our idea of the struct after a patch. The
// guard is checked after every call; if it changed, the layout is stale and
// reporting is switched off rather than trusting the data.
constexpr std::size_t kGuardBytes = 0x100;
constexpr unsigned char kGuardFill = 0xA5;

bool CallGetReplicaGuarded(const void* item, ItemReplicaInfo* out) {
    // No C++ objects with destructors may live in this function: MSVC's
    // structured exception handling cannot unwind them.
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

// Why a tooltip-line vector was rejected (for the one-time diagnostic).
enum class LinesVerdict { Ok, NullVector, BadSize, BadClass, TooLong, Fault };

const char* VerdictName(LinesVerdict verdict) {
    switch (verdict) {
        case LinesVerdict::Ok: return "ok";
        case LinesVerdict::NullVector: return "null vector";
        case LinesVerdict::BadSize: return "byte span is not a whole number of GameTextLine";
        case LinesVerdict::BadClass: return "text class outside 0..255";
        case LinesVerdict::TooLong: return "string length implausible";
        case LinesVerdict::Fault: return "access violation while reading";
    }
    return "?";
}

// Copies pointers to the game's tooltip lines without touching their memory
// management. On success *count holds the number of lines.
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
        if (bytes < 0 || bytes % sizeof(GameTextLine) != 0 ||
            vector->end < vector->last) {
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

// Copy up to `size` bytes from an address that may not be readable.
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

// Logs everything needed to work out the real layout: the vector header,
// the first bytes of its storage, and any wide strings reachable from
// pointer-sized fields of the first element.
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
        for (std::size_t offset = 0; offset + 8 <= 0x80; offset += 8) {
            const void* candidate = nullptr;
            std::memcpy(&candidate, element + offset, sizeof(candidate));
            wchar_t text[48] = {};
            if (candidate == nullptr || !SafeCopy(text, candidate, sizeof(text) - 2)) {
                continue;
            }
            std::string printable;
            for (wchar_t character : text) {
                if (character == 0) break;
                printable += (character >= 32 && character < 127) ? static_cast<char>(character) : '.';
            }
            if (printable.size() >= 3) {
                report += "\n  pointer at +" + std::to_string(offset) + " -> \"" + printable + "\"";
            }
        }
        // Inline (small-string) text directly inside the element.
        for (std::size_t offset = 0; offset + 16 <= 0x80; offset += 8) {
            std::string printable;
            for (std::size_t index = 0; index < 8; ++index) {
                wchar_t character;
                std::memcpy(&character, element + offset + index * 2, 2);
                if (character == 0) break;
                printable += (character >= 32 && character < 127) ? static_cast<char>(character) : '.';
            }
            if (printable.size() >= 3) {
                report += "\n  inline text at +" + std::to_string(offset) + ": \"" + printable + "\"";
            }
        }
    } else {
        report += "\nfirst pointer unreadable";
    }
    Log(report);
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
    WideCharToMultiByte(CP_UTF8, 0, text, static_cast<int>(length), result.data(),
                        size, nullptr, nullptr);
    return result;
}

std::string Clean(const std::string& value) {
    std::string result = value;
    for (char& character : result) {
        if (character == '\t' || character == '\r' || character == '\n') {
            character = ' ';
        }
    }
    return result;
}

// Appends "\t<class>:<text>" for each tooltip line.
void AppendLines(const void* lines, std::string* message) {
    if (lines == nullptr || g_linesDisabled.load()) {
        return;
    }
    RawLine raw[kMaxLines];
    int count = 0;
    const LinesVerdict verdict = SnapshotLinesGuarded(lines, raw, &count);
    if (verdict != LinesVerdict::Ok) {
        g_linesDisabled.store(true);
        LogLinesDiagnostic(lines, verdict);
        Report(std::string("GG1\terror\ttooltip text layout not recognised (") +
               VerdictName(verdict) + "); reporting records only. Details in gg_hook.log");
        return;
    }
    for (int index = 0; index < count; ++index) {
        *message += "\t" + std::to_string(raw[index].textClass) + ":" +
                    Clean(ToUtf8(raw[index].text, raw[index].length));
    }
}

void ReportItem(const void* item, const void* lines, std::uint64_t calls) {
    alignas(ItemReplicaInfo) unsigned char storage[sizeof(ItemReplicaInfo) + kGuardBytes];
    std::memset(storage + sizeof(ItemReplicaInfo), kGuardFill, kGuardBytes);
    auto* info = new (storage) ItemReplicaInfo();

    bool ok = CallGetReplicaGuarded(item, info);
    bool guardIntact = true;
    for (std::size_t index = 0; index < kGuardBytes; ++index) {
        if (storage[sizeof(ItemReplicaInfo) + index] != kGuardFill) {
            guardIntact = false;
            break;
        }
    }

    if (!ok || !guardIntact) {
        g_reportingDisabled.store(true);
        const char* reason = !ok
            ? "GetItemReplicaInfo raised an exception"
            : "Game.dll wrote past ItemReplicaInfo: layout changed in this game version";
        Log(std::string("tooltip: reporting disabled: ") + reason);
        Report(std::string("GG1\terror\t") + reason);
        // Leak rather than destroy: after a fault the strings may be garbage.
        return;
    }

    std::string line = "GG1\titem\t" + std::to_string(calls) + "\t" +
                       std::to_string(info->seed) + "\t" + Clean(info->baseRecord) +
                       "\t" + Clean(info->prefixRecord) + "\t" + Clean(info->suffixRecord) +
                       "\t" + Clean(info->modifierRecord) + "\t" + Clean(info->materiaRecord) +
                       "\t" + Clean(info->relicBonus) + "\t" + Clean(info->enchantmentRecord) +
                       "\t" + Clean(info->transmuteRecord) + "\t" + Clean(info->ascendant1) +
                       "\t" + Clean(info->ascendant2);
    info->~ItemReplicaInfo();
    AppendLines(lines, &line);
    Report(std::move(line));
}

void OnTooltipBuilt(const void* item, const void* lines) {
    const std::uint64_t calls = ++g_calls;
    if (item == nullptr || g_reportingDisabled.load()) {
        return;
    }
    const ULONGLONG now = GetTickCount64();
    {
        std::lock_guard<std::mutex> lock(g_dedupeMutex);
        if (item == g_lastItem && now - g_lastReportTick < kRepeatAfterMs) {
            g_lastReportTick = now;
            return;
        }
        g_lastItem = item;
        g_lastReportTick = now;
    }
    try {
        ReportItem(item, lines, calls);
    } catch (...) {
        // With /EHa this also catches access violations. Never let our code
        // take the game down.
        g_reportingDisabled.store(true);
        Log("tooltip: unexpected exception while reading item; reporting disabled");
    }
}

void HookedGetUIDisplayText4(const void* self, const void* character, void* lines,
                             bool includeSetBonusDetails) {
    g_original4(self, character, lines, includeSetBonusDetails);
    OnTooltipBuilt(self, lines);
}

void HookedGetUIDisplayText3(const void* self, const void* character, void* lines) {
    g_original3(self, character, lines);
    OnTooltipBuilt(self, lines);
}

// Detours must be told about every thread that might be executing the bytes
// it is about to patch.
std::vector<HANDLE> UpdateAllOtherThreads() {
    std::vector<HANDLE> handles;
    const DWORD process = GetCurrentProcessId();
    const DWORD self = GetCurrentThreadId();
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return handles;
    }
    THREADENTRY32 entry{};
    entry.dwSize = sizeof(entry);
    for (BOOL more = Thread32First(snapshot, &entry); more;
         more = Thread32Next(snapshot, &entry)) {
        if (entry.th32OwnerProcessID != process || entry.th32ThreadID == self) {
            continue;
        }
        HANDLE thread = OpenThread(
            THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_SET_CONTEXT, FALSE,
            entry.th32ThreadID);
        if (thread != nullptr) {
            DetourUpdateThread(thread);
            handles.push_back(thread);
        }
    }
    CloseHandle(snapshot);
    return handles;
}

}  // namespace

bool InstallTooltipHook(std::string* detail) {
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

    void* target = reinterpret_cast<void*>(
        GetProcAddress(gameDll, game::kItemEquipmentGetUIDisplayText4));
    void** original = reinterpret_cast<void**>(&g_original4);
    void* replacement = reinterpret_cast<void*>(&HookedGetUIDisplayText4);
    const char* variant = "4-argument";
    if (target == nullptr) {
        target = reinterpret_cast<void*>(
            GetProcAddress(gameDll, game::kItemEquipmentGetUIDisplayText3));
        original = reinterpret_cast<void**>(&g_original3);
        replacement = reinterpret_cast<void*>(&HookedGetUIDisplayText3);
        variant = "3-argument";
    }
    if (target == nullptr) {
        *detail = "Game.dll has no known ItemEquipment::GetUIDisplayText export";
        return false;
    }
    *original = target;

    LONG result = DetourTransactionBegin();
    std::vector<HANDLE> threads;
    if (result == NO_ERROR) {
        threads = UpdateAllOtherThreads();
        result = DetourAttach(original, replacement);
        if (result == NO_ERROR) {
            result = DetourTransactionCommit();
        } else {
            DetourTransactionAbort();
        }
    }
    for (HANDLE thread : threads) {
        CloseHandle(thread);
    }
    if (result != NO_ERROR) {
        *original = nullptr;
        *detail = "Detours failed to attach (error " + std::to_string(result) + ")";
        return false;
    }
    *detail = std::string("hooked ItemEquipment::GetUIDisplayText (") + variant + ")";
    return true;
}

std::uint64_t TooltipCallCount() {
    return g_calls.load();
}

}  // namespace gg
