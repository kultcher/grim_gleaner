#include "tooltip_hook.h"

#include <windows.h>

#include <atomic>
#include <cstdio>
#include <mutex>
#include <vector>

#include "game_access.h"
#include "game_types.h"
#include "hook_log.h"
#include "hook_util.h"
#include "live_table.h"
#include "reporter.h"
#include "stat_core.h"

namespace gg {
namespace {

// x64 has a single calling convention; `this` arrives first.
using GetUIDisplayText4Fn = void (*)(const void* self, const void* character,
                                     void* lines, bool detailed);
using GetUIDisplayText3Fn = void (*)(const void* self, const void* character,
                                     void* lines);

GetUIDisplayText4Fn g_original4 = nullptr;
GetUIDisplayText3Fn g_original3 = nullptr;

std::atomic<std::uint64_t> g_calls{0};
// Each optional behaviour switches itself off independently on any sign of
// trouble, leaving the game untouched.
std::atomic<bool> g_reportingDisabled{false};
std::atomic<bool> g_linesDisabled{false};
std::atomic<bool> g_detailDisabled{false};

// Text class for the injected "A 87%" line: the class 1.3.1 uses for item
// bonus lines, so it renders like them.
constexpr int kLabelTextClass = 0x13;

// Drop only a byte-identical report within this window.
constexpr ULONGLONG kDuplicateWindowMs = 250;
std::mutex g_dedupeMutex;
std::string g_lastBody;
ULONGLONG g_lastReportTick = 0;

std::string Clean(std::string value) {
    for (char& character : value) {
        if (character == '\t' || character == '\r' || character == '\n') {
            character = ' ';
        }
    }
    return value;
}

std::string Format(double value) {
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "%.6f", value);
    return buffer;
}

void DisableWith(std::atomic<bool>& flag, const std::string& message) {
    if (!flag.exchange(true)) {
        Log("tooltip: " + message);
        Report("GG1\terror\t" + message);
    }
}

void OnTooltipBuilt(const void* item, const void* character, void* lines,
                    bool detailedAlready, bool canBuildDetailed) {
    const std::uint64_t calls = ++g_calls;
    if (item == nullptr || g_reportingDisabled.load()) {
        return;
    }

    game_access::ItemSnapshot snapshot;
    switch (game_access::ReadItem(item, &snapshot)) {
        case game_access::ReadResult::Ok:
            break;
        case game_access::ReadResult::Fault:
            DisableWith(g_reportingDisabled, "GetItemReplicaInfo raised an exception; reporting disabled");
            return;
        case game_access::ReadResult::LayoutChanged:
            DisableWith(g_reportingDisabled,
                        "Game.dll wrote past ItemReplicaInfo: layout changed in this game version");
            return;
    }

    std::vector<core::TooltipLine> displayed;
    if (!g_linesDisabled.load()) {
        const auto verdict = game_access::ReadLines(lines, &displayed);
        if (verdict != game_access::LinesVerdict::Ok) {
            game_access::LogLinesDiagnostic(lines, verdict);
            DisableWith(g_linesDisabled, std::string("tooltip text layout not recognised (") +
                                             game_access::VerdictName(verdict) +
                                             "); reporting records only");
            displayed.clear();
        }
    }

    const auto table = CurrentTable();
    std::vector<core::TooltipLine> evaluated = displayed;
    bool detailUsed = detailedAlready;
    if (table && table->detailPass() && canBuildDetailed && !detailedAlready &&
        !g_detailDisabled.load() && !g_linesDisabled.load()) {
        std::vector<core::TooltipLine> detailed;
        const auto result = game_access::ReadDetailedLines(
            reinterpret_cast<game_access::BuildTooltipFn>(g_original4), item, character,
            &detailed);
        if (result == game_access::DetailResult::Ok) {
            evaluated = std::move(detailed);
            detailUsed = true;
        } else if (result == game_access::DetailResult::Failed) {
            DisableWith(g_detailDisabled, "detailed tooltip pass failed; roll ranges disabled");
        }
    }

    std::string attributes;
    if (table) {
        const core::Relevance relevance = table->Score(
            {snapshot.baseRecord, snapshot.prefixRecord, snapshot.suffixRecord});
        const core::RollQualityResult quality = table->RollQuality(evaluated);
        const std::string label = core::GradeTable::Label(relevance.grade, quality);
        const bool injected =
            table->injectLabel() &&
            game_access::AppendShortLine(lines, kLabelTextClass, label);
        attributes = "\t@grade=" + relevance.grade + "\t@score=" + Format(relevance.score) +
                     "\t@matched=" + std::to_string(relevance.matched) +
                     "\t@total=" + std::to_string(relevance.total) +
                     "\t@rarity=" + relevance.rarity +
                     "\t@rq=" + (quality.hasValue ? Format(quality.value) : std::string("-")) +
                     "\t@label=" + label + "\t@table=" + table->id() +
                     "\t@detail=" + (detailUsed ? "1" : "0") +
                     "\t@injected=" + (injected ? "1" : "0");
    }

    std::string body = std::to_string(snapshot.seed) + "\t" + Clean(snapshot.baseRecord) +
                       "\t" + Clean(snapshot.prefixRecord) + "\t" +
                       Clean(snapshot.suffixRecord) + "\t" + Clean(snapshot.modifierRecord) +
                       "\t" + Clean(snapshot.materiaRecord) + "\t" +
                       Clean(snapshot.relicBonus) + "\t" + Clean(snapshot.enchantmentRecord) +
                       "\t" + Clean(snapshot.transmuteRecord) + "\t" +
                       Clean(snapshot.ascendant1) + "\t" + Clean(snapshot.ascendant2) +
                       attributes;
    for (const core::TooltipLine& line : evaluated) {
        body += "\t" + std::to_string(line.textClass) + ":" + Clean(line.text);
    }

    const ULONGLONG now = GetTickCount64();
    {
        std::lock_guard<std::mutex> lock(g_dedupeMutex);
        if (body == g_lastBody && now - g_lastReportTick < kDuplicateWindowMs) {
            return;
        }
        g_lastBody = body;
        g_lastReportTick = now;
    }
    Report("GG1\titem\t" + std::to_string(calls) + "\t" + body);
}

void SafeOnTooltipBuilt(const void* item, const void* character, void* lines,
                        bool detailedAlready, bool canBuildDetailed) {
    try {
        OnTooltipBuilt(item, character, lines, detailedAlready, canBuildDetailed);
    } catch (...) {
        // With /EHa this also catches access violations. Never let our code
        // take the game down.
        DisableWith(g_reportingDisabled, "unexpected exception in tooltip hook; reporting disabled");
    }
}

void HookedGetUIDisplayText4(const void* self, const void* character, void* lines,
                             bool detailed) {
    g_original4(self, character, lines, detailed);
    SafeOnTooltipBuilt(self, character, lines, detailed, true);
}

void HookedGetUIDisplayText3(const void* self, const void* character, void* lines) {
    g_original3(self, character, lines);
    SafeOnTooltipBuilt(self, character, lines, false, false);
}

}  // namespace

bool InstallTooltipHook(std::string* detail) {
    if (!game_access::Initialize(detail)) {
        return false;
    }
    HMODULE gameDll = GetModuleHandleW(L"Game.dll");
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
    std::string error;
    if (!AttachHook(original, replacement, &error)) {
        *original = nullptr;
        *detail = error;
        return false;
    }
    *detail = std::string("hooked ItemEquipment::GetUIDisplayText (") + variant + ")";
    return true;
}

std::uint64_t TooltipCallCount() {
    return g_calls.load();
}

}  // namespace gg
