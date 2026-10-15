#pragma once
// Game-independent live evaluation: tooltip line normalisation, grade table
// loading, whole-item relevance, roll quality, tooltip label and the loot
// filter decision.
//
// This is a line-for-line port of the Python reference
// (gd_affix_relevance/live/stat_lines.py, live/scoring.py and
// scoring/catalog_scorer.py:score_semantic_stat_ids). It has no Windows or
// game dependencies so tests/test_native_core.py can compile it with a host
// compiler and compare it with Python on real data.

#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace gg::core {

std::string StripColorCodes(std::string_view text);
std::string LineKey(std::string_view text);
bool IsPetHeading(const std::string& key);

struct ParsedLine {
    std::string key;
    std::vector<double> values;
    bool hasRange = false;
    double low = 0.0;
    double high = 0.0;
};
ParsedLine ParseLine(std::string_view text);

struct Relevance {
    std::string grade = "F";
    double score = 0.0;
    int matched = 0;
    int total = 0;
    std::string rarity = "other";
};

struct RollQualityResult {
    bool hasValue = false;
    double value = 0.0;
    int rolledStats = 0;
};

// One tooltip line as the game built it.
struct TooltipLine {
    int textClass;
    std::string text;  // UTF-8
};

class GradeTable {
public:
    // Parses the GGT1 text format (see live/grade_table.py). On failure
    // returns false, sets *error and leaves the table empty.
    bool Load(std::string_view text, std::string* error);

    bool loaded() const { return loaded_; }
    const std::string& id() const { return id_; }
    bool filterEnabled() const { return filterEnabled_; }
    bool injectLabel() const { return injectLabel_; }
    bool detailPass() const { return detailPass_; }

    Relevance Score(const std::vector<std::string>& records) const;
    RollQualityResult RollQuality(const std::vector<TooltipLine>& lines) const;
    bool ShouldHide(const std::string& grade, const std::string& rarity) const;

    // At most 7 characters ("A 87%", "S++100%"): fits MSVC std::wstring's
    // inline buffer, so injecting it never allocates.
    static std::string Label(const std::string& grade, const RollQualityResult& quality);

    static std::string NormalizeRecord(std::string_view record);

private:
    struct Stat {
        double points = 0.0;
        int weight = 0;
    };
    struct RecordStat {
        int stat;
        bool hasMultiplier;
        double multiplier;
    };
    struct Record {
        std::string rarity;
        std::vector<RecordStat> stats;
    };

    bool loaded_ = false;
    std::string id_;
    double adjustment_ = 1.0;
    std::vector<std::pair<std::string, double>> grades_;  // highest first
    bool filterEnabled_ = false;
    bool injectLabel_ = false;
    bool detailPass_ = false;
    std::unordered_map<std::string, std::string> hideBelow_;
    std::vector<Stat> stats_;
    std::unordered_map<std::string, Record> records_;
    std::unordered_map<std::string, int> lineStats_;
    std::unordered_map<std::string, int> petLineStats_;
};

int GradeRank(const std::string& grade);  // F=0 ... S++=7, unknown=-1

}  // namespace gg::core
