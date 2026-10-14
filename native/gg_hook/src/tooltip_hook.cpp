#include "tooltip_hook.h"

#include <windows.h>
#include <tlhelp32.h>

#include <detours.h>

#include <atomic>
#include <cstring>
#include <mutex>
#include <new>
#include <vector>

#include "game_types.h"
#include "hook_log.h"
#include "reporter.h"

namespace gg {
namespace {

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

std::string Clean(const std::string& value) {
    std::string result = value;
    for (char& character : result) {
        if (character == '\t' || character == '\r' || character == '\n') {
            character = ' ';
        }
    }
    return result;
}

void ReportItem(const void* item, std::uint64_t calls) {
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
    Report(std::move(line));
}

void OnTooltipBuilt(const void* item) {
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
        ReportItem(item, calls);
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
    OnTooltipBuilt(self);
}

void HookedGetUIDisplayText3(const void* self, const void* character, void* lines) {
    g_original3(self, character, lines);
    OnTooltipBuilt(self);
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
