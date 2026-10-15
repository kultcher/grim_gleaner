#include "loot_filter_hook.h"

#include <windows.h>

#include <atomic>
#include <cstdint>
#include <string>
#include <mutex>
#include <unordered_map>

#include "game_access.h"
#include "game_types.h"
#include "hook_log.h"
#include "hook_util.h"
#include "live_table.h"
#include "reporter.h"

namespace gg {
namespace {

// bool GAME::Item::PassLootFilter(GAME::InGameUIActorCapture::ItemIgnore) const
using PassLootFilterFn = bool (*)(const void* self, int ignore);
PassLootFilterFn g_original = nullptr;
std::atomic<bool> g_disabled{false};

// The game asks about every visible ground item, likely every frame. Cache
// each item's decision and re-read it at most once a second (an item address
// can be reused by a new drop, so decisions must not live long).
constexpr ULONGLONG kRecheckMs = 1000;
constexpr ULONGLONG kForgetMs = 60000;
constexpr std::size_t kPruneAbove = 4096;

struct Decision {
    std::string tableId;
    ULONGLONG checkedAt;
    bool hide;
};
std::mutex g_cacheMutex;
std::unordered_map<const void*, Decision> g_cache;

void Disable(const std::string& message) {
    if (!g_disabled.exchange(true)) {
        Log("loot filter: " + message);
        Report("GG1\terror\tloot filter disabled: " + message);
    }
}

bool ShouldHide(const void* item) {
    const auto table = CurrentTable();
    if (!table || !table->filterEnabled()) {
        return false;
    }
    const ULONGLONG now = GetTickCount64();
    bool hadPrevious = false;
    Decision previous;
    {
        std::lock_guard<std::mutex> lock(g_cacheMutex);
        const auto found = g_cache.find(item);
        if (found != g_cache.end()) {
            if (found->second.tableId == table->id() &&
                now - found->second.checkedAt < kRecheckMs) {
                return found->second.hide;
            }
            hadPrevious = true;
            previous = found->second;
        }
    }

    game_access::ItemSnapshot snapshot;
    if (game_access::ReadItem(item, &snapshot) != game_access::ReadResult::Ok) {
        Disable("could not read an item's records");
        return false;
    }
    const core::Relevance relevance =
        table->Score({snapshot.baseRecord, snapshot.prefixRecord, snapshot.suffixRecord});
    const bool hide = table->ShouldHide(relevance.grade, relevance.rarity);

    {
        std::lock_guard<std::mutex> lock(g_cacheMutex);
        if (g_cache.size() > kPruneAbove) {
            for (auto it = g_cache.begin(); it != g_cache.end();) {
                it = now - it->second.checkedAt > kForgetMs ? g_cache.erase(it) : std::next(it);
            }
        }
        g_cache[item] = Decision{table->id(), now, hide};
    }
    if (!hadPrevious || previous.hide != hide || previous.tableId != table->id()) {
        Report("GG1\tfilter\t" + std::to_string(snapshot.seed) + "\t" + snapshot.baseRecord +
               "\t" + snapshot.prefixRecord + "\t" + snapshot.suffixRecord + "\t" +
               relevance.grade + "\t" + relevance.rarity + "\t" + (hide ? "1" : "0") + "\t" +
               table->id());
    }
    return hide;
}

// Diagnostic: how the game calls PassLootFilter, to learn which ItemIgnore
// value (if any) means "show hidden items". Counts per argument value of the
// game's own verdict and of our overrides, logged every 2 seconds while they
// change, with the Alt key state at that moment.
constexpr int kIgnoreBuckets = 17;  // values 0..15, then "other"
std::atomic<std::uint32_t> g_gamePass[kIgnoreBuckets];
std::atomic<std::uint32_t> g_gameFail[kIgnoreBuckets];
std::atomic<std::uint32_t> g_weHid[kIgnoreBuckets];
std::atomic<ULONGLONG> g_lastDiagnostic{0};
std::uint32_t g_loggedTotal = 0;  // guarded by g_diagnosticMutex
std::mutex g_diagnosticMutex;

void CountCall(int ignore, bool gamePass, bool weHid) {
    const int bucket = (ignore >= 0 && ignore < kIgnoreBuckets - 1) ? ignore : kIgnoreBuckets - 1;
    (gamePass ? g_gamePass : g_gameFail)[bucket].fetch_add(1, std::memory_order_relaxed);
    if (weHid) {
        g_weHid[bucket].fetch_add(1, std::memory_order_relaxed);
    }
    const ULONGLONG now = GetTickCount64();
    if (now - g_lastDiagnostic.load(std::memory_order_relaxed) < 2000) {
        return;
    }
    std::unique_lock<std::mutex> lock(g_diagnosticMutex, std::try_to_lock);
    if (!lock.owns_lock()) {
        return;
    }
    g_lastDiagnostic.store(now);
    std::string message = "loot filter calls (ignore=value: game pass/fail, we hid)";
    std::uint32_t total = 0;
    for (int index = 0; index < kIgnoreBuckets; ++index) {
        const std::uint32_t pass = g_gamePass[index].exchange(0);
        const std::uint32_t fail = g_gameFail[index].exchange(0);
        const std::uint32_t hid = g_weHid[index].exchange(0);
        if (pass + fail == 0) {
            continue;
        }
        total += pass + fail;
        message += " | " + (index == kIgnoreBuckets - 1 ? std::string("other") : std::to_string(index)) +
                   ": " + std::to_string(pass) + "/" + std::to_string(fail) + ", " +
                   std::to_string(hid);
    }
    const bool altDown = (GetAsyncKeyState(VK_MENU) & 0x8000) != 0;
    message += altDown ? " | Alt held" : " | Alt up";
    if (total > 0 || g_loggedTotal > 0) {
        Log(message);
    }
    g_loggedTotal = total;
}

bool HookedPassLootFilter(const void* self, int ignore) {
    const bool pass = g_original(self, ignore);
    bool result = pass;
    // Only ever turn a pass into a fail, never the reverse.
    if (pass && self != nullptr && !g_disabled.load()) {
        try {
            result = !ShouldHide(self);
        } catch (...) {
            Disable("unexpected exception");
            result = pass;
        }
    }
    try {
        CountCall(ignore, pass, pass && !result);
    } catch (...) {
    }
    return result;
}

}  // namespace

bool InstallLootFilterHook(std::string* detail) {
    HMODULE gameDll = GetModuleHandleW(L"Game.dll");
    if (gameDll == nullptr) {
        *detail = "Game.dll is not loaded";
        return false;
    }
    void* target = reinterpret_cast<void*>(GetProcAddress(gameDll, game::kItemPassLootFilter));
    if (target == nullptr) {
        *detail = "Game.dll has no Item::PassLootFilter export";
        return false;
    }
    g_original = reinterpret_cast<PassLootFilterFn>(target);
    std::string error;
    if (!AttachHook(reinterpret_cast<void**>(&g_original),
                    reinterpret_cast<void*>(&HookedPassLootFilter), &error)) {
        g_original = nullptr;
        *detail = error;
        return false;
    }
    *detail = "hooked Item::PassLootFilter";
    return true;
}

}  // namespace gg
