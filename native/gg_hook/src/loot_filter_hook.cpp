#include "loot_filter_hook.h"

#include <windows.h>

#include <atomic>
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

bool HookedPassLootFilter(const void* self, int ignore) {
    const bool pass = g_original(self, ignore);
    // Only ever turn a pass into a fail, never the reverse.
    if (!pass || self == nullptr || g_disabled.load()) {
        return pass;
    }
    try {
        return !ShouldHide(self);
    } catch (...) {
        Disable("unexpected exception");
        return pass;
    }
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
