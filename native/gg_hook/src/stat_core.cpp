#include "stat_core.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <regex>
#include <set>
#include <unordered_set>

namespace gg::core {
namespace {

// Same patterns as live/stat_lines.py (all ASCII). Compiled once.
const std::regex& ColorCode() {
    static const std::regex pattern(R"(\{\^.\}|\^[A-Za-z])");
    return pattern;
}
const std::regex& RangeSuffix() {
    static const std::regex pattern(
        R"(\[ *([0-9]+(?:\.[0-9]+)?) *(?:- *([0-9]+(?:\.[0-9]+)?) *)?\] *$)");
    return pattern;
}
const std::regex& Number() {
    static const std::regex pattern(R"([0-9]+(?:\.[0-9]+)?)");
    return pattern;
}
const std::regex& SignedHash() {
    static const std::regex pattern(R"([+-] *#)");
    return pattern;
}
const std::regex& HashRange() {
    static const std::regex pattern(R"(# *- *#)");
    return pattern;
}
const std::regex& DurationSuffix() {
    static const std::regex pattern(R"( (?:over|for) # seconds?$)");
    return pattern;
}
const std::regex& Spaces() {
    static const std::regex pattern(R"([ \t\n\r\f\v]+)");
    return pattern;
}

std::string Strip(const std::string& text) {
    const char* whitespace = " \t\n\r\f\v";
    const auto first = text.find_first_not_of(whitespace);
    if (first == std::string::npos) {
        return {};
    }
    const auto last = text.find_last_not_of(whitespace);
    return text.substr(first, last - first + 1);
}

// Mirrors _finish_key in stat_lines.py, step for step.
std::string FinishKey(std::string text) {
    text.erase(std::remove(text.begin(), text.end(), '('), text.end());
    text.erase(std::remove(text.begin(), text.end(), ')'), text.end());
    text = Strip(std::regex_replace(text, Spaces(), " "));
    std::string previous;
    do {
        previous = text;
        text = std::regex_replace(text, HashRange(), "#");
    } while (previous != text);
    text = std::regex_replace(text, SignedHash(), "#");
    for (char& character : text) {
        if (character >= 'A' && character <= 'Z') {
            character = static_cast<char>(character - 'A' + 'a');
        }
    }
    return std::regex_replace(text, DurationSuffix(), "",
                              std::regex_constants::format_first_only);
}

std::vector<std::string> Split(std::string_view line, char separator) {
    std::vector<std::string> parts;
    std::size_t start = 0;
    while (true) {
        const auto end = line.find(separator, start);
        parts.emplace_back(line.substr(start, end == std::string_view::npos ? end : end - start));
        if (end == std::string_view::npos) {
            break;
        }
        start = end + 1;
    }
    return parts;
}

bool ParseDouble(const std::string& text, double* value) {
    if (text.empty()) {
        return false;
    }
    char* end = nullptr;
    *value = std::strtod(text.c_str(), &end);
    return end != nullptr && *end == '\0';
}

bool ParseInt(const std::string& text, int* value) {
    double parsed = 0.0;
    if (!ParseDouble(text, &parsed)) {
        return false;
    }
    *value = static_cast<int>(parsed);
    return static_cast<double>(*value) == parsed;
}

}  // namespace

std::string StripColorCodes(std::string_view text) {
    return std::regex_replace(std::string(text), ColorCode(), "");
}

std::string LineKey(std::string_view text) {
    std::string plain = StripColorCodes(text);
    plain = std::regex_replace(plain, RangeSuffix(), "");
    plain = std::regex_replace(plain, Number(), "#");
    return FinishKey(plain);
}

bool IsPetHeading(const std::string& key) {
    if (key.find('#') != std::string::npos) {
        return false;
    }
    std::string word;
    auto isPet = [](const std::string& candidate) {
        return candidate == "pet" || candidate == "pets";
    };
    for (char character : key) {
        if (character >= 'a' && character <= 'z') {
            word += character;
        } else {
            if (isPet(word)) {
                return true;
            }
            word.clear();
        }
    }
    return isPet(word);
}

ParsedLine ParseLine(std::string_view text) {
    ParsedLine parsed;
    parsed.key = LineKey(text);
    std::string plain = Strip(StripColorCodes(text));
    std::smatch match;
    if (std::regex_search(plain, match, RangeSuffix())) {
        const double first = std::strtod(match[1].str().c_str(), nullptr);
        const double second =
            match[2].matched ? std::strtod(match[2].str().c_str(), nullptr) : first;
        parsed.hasRange = true;
        parsed.low = std::min(first, second);
        parsed.high = std::max(first, second);
        plain = Strip(plain.substr(0, static_cast<std::size_t>(match.position(0))));
    }
    for (auto it = std::sregex_iterator(plain.begin(), plain.end(), Number());
         it != std::sregex_iterator(); ++it) {
        parsed.values.push_back(std::strtod(it->str().c_str(), nullptr));
    }
    return parsed;
}

std::string GradeTable::NormalizeRecord(std::string_view record) {
    std::string result = Strip(std::string(record));
    for (char& character : result) {
        if (character == '\\') {
            character = '/';
        } else if (character >= 'A' && character <= 'Z') {
            character = static_cast<char>(character - 'A' + 'a');
        }
    }
    return result;
}

bool GradeTable::Load(std::string_view text, std::string* error) {
    *this = GradeTable();
    auto fail = [&](const std::string& message) {
        *this = GradeTable();
        if (error != nullptr) {
            *error = message;
        }
        return false;
    };
    std::size_t lineNumber = 0;
    bool sawHeader = false;
    bool sawEnd = false;
    for (std::string raw : Split(text, '\n')) {
        ++lineNumber;
        if (!raw.empty() && raw.back() == '\r') {
            raw.pop_back();
        }
        if (raw.empty()) {
            continue;
        }
        const auto fields = Split(raw, '\t');
        const std::string& kind = fields[0];
        const std::string where = " (line " + std::to_string(lineNumber) + ")";
        if (!sawHeader) {
            if (kind != "GGT1" || fields.size() < 2) {
                return fail("not a GGT1 grade table" + where);
            }
            id_ = fields[1];
            sawHeader = true;
        } else if (kind == "adjust" && fields.size() == 2) {
            if (!ParseDouble(fields[1], &adjustment_)) return fail("bad adjust" + where);
        } else if (kind == "grade" && fields.size() == 3) {
            double minimum = 0.0;
            if (!ParseDouble(fields[2], &minimum)) return fail("bad grade" + where);
            grades_.emplace_back(fields[1], minimum);
        } else if (kind == "filter" && fields.size() == 2) {
            filterEnabled_ = fields[1] == "1";
        } else if (kind == "inject" && fields.size() == 2) {
            injectLabel_ = fields[1] == "1";
        } else if (kind == "detail" && fields.size() == 2) {
            detailPass_ = fields[1] == "1";
        } else if (kind == "hide" && fields.size() == 3) {
            hideBelow_[fields[1]] = fields[2];
        } else if (kind == "stat" && fields.size() == 4) {
            int index = 0;
            Stat stat;
            if (!ParseInt(fields[1], &index) || !ParseDouble(fields[2], &stat.points) ||
                !ParseInt(fields[3], &stat.weight) ||
                index != static_cast<int>(stats_.size())) {
                return fail("bad stat" + where);
            }
            stats_.push_back(stat);
        } else if (kind == "rec" && fields.size() == 4) {
            Record record;
            record.rarity = fields[2];
            if (!fields[3].empty()) {
                for (const std::string& cell : Split(fields[3], ',')) {
                    RecordStat stat{0, false, 1.0};
                    const auto star = cell.find('*');
                    if (!ParseInt(cell.substr(0, star), &stat.stat) || stat.stat < 0 ||
                        stat.stat >= static_cast<int>(stats_.size())) {
                        return fail("bad record stat" + where);
                    }
                    if (star != std::string::npos) {
                        stat.hasMultiplier = true;
                        if (!ParseDouble(cell.substr(star + 1), &stat.multiplier)) {
                            return fail("bad multiplier" + where);
                        }
                    }
                    record.stats.push_back(stat);
                }
            }
            records_[fields[1]] = std::move(record);
        } else if ((kind == "line" || kind == "petline") && fields.size() == 3) {
            int index = 0;
            if (!ParseInt(fields[2], &index) || index < 0 ||
                index >= static_cast<int>(stats_.size())) {
                return fail("bad line stat" + where);
            }
            (kind == "line" ? lineStats_ : petLineStats_)[fields[1]] = index;
        } else if (kind == "end") {
            sawEnd = true;
            break;
        } else {
            return fail("unrecognised line" + where);
        }
    }
    if (!sawHeader || !sawEnd) {
        return fail("grade table is incomplete");
    }
    loaded_ = true;
    return true;
}

Relevance GradeTable::Score(const std::vector<std::string>& records) const {
    // Union of the records' stats. A stat's multiplier is the strongest one
    // any record provides (records without magnitude data provide none).
    std::unordered_map<int, double> multiplier;
    std::set<int> union_;
    const Record* base = nullptr;
    std::vector<const Record*> affixes;
    for (std::size_t index = 0; index < records.size(); ++index) {
        if (records[index].empty()) {
            continue;
        }
        const auto found = records_.find(NormalizeRecord(records[index]));
        if (found == records_.end()) {
            continue;
        }
        const Record& record = found->second;
        if (index == 0) {
            base = &record;
        } else {
            affixes.push_back(&record);
        }
        for (const RecordStat& stat : record.stats) {
            union_.insert(stat.stat);
            if (stat.hasMultiplier) {
                auto existing = multiplier.find(stat.stat);
                if (existing == multiplier.end() || stat.multiplier > existing->second) {
                    multiplier[stat.stat] = stat.multiplier;
                }
            }
        }
    }

    Relevance result;
    double relevancePoints = 0.0;
    for (int stat : union_) {
        ++result.total;
        if (stats_[stat].weight > 0) {
            ++result.matched;
            const auto found = multiplier.find(stat);
            relevancePoints +=
                stats_[stat].points * (found == multiplier.end() ? 1.0 : found->second);
        }
    }
    const double coverage =
        result.total ? static_cast<double>(result.matched) / result.total : 0.0;
    result.score = relevancePoints * (0.70 + 0.30 * coverage) * adjustment_;
    result.grade = "F";
    for (const auto& [grade, minimum] : grades_) {
        if (result.score >= minimum) {
            result.grade = grade;
            break;
        }
    }

    // Rarity class (live/scoring.py:item_rarity_class).
    const std::string baseClass = base ? base->rarity : "other";
    if (baseClass == "monster_infrequent" || baseClass == "epic" || baseClass == "legendary") {
        result.rarity = baseClass;
    } else {
        bool anyRare = false;
        for (const Record* affix : affixes) {
            anyRare = anyRare || affix->rarity == "rare";
        }
        result.rarity = anyRare ? "rare" : (!affixes.empty() ? "magic" : baseClass);
    }
    return result;
}

RollQualityResult GradeTable::RollQuality(const std::vector<TooltipLine>& lines) const {
    // Mirrors stat_lines.match_tooltip_stats + scoring.roll_quality.
    constexpr int kNoPetSection = -2;
    constexpr int kPetSectionPending = -1;
    int petClass = kNoPetSection;
    double weighted = 0.0;
    double totalPoints = 0.0;
    RollQualityResult result;
    for (const TooltipLine& line : lines) {
        const ParsedLine parsed = ParseLine(line.text);
        const auto found = lineStats_.find(parsed.key);
        int stat = found == lineStats_.end() ? -1 : found->second;
        if (stat < 0 && IsPetHeading(parsed.key)) {
            petClass = kPetSectionPending;
            continue;
        }
        if (petClass == kPetSectionPending) {
            petClass = line.textClass;
        } else if (petClass != kNoPetSection && line.textClass != petClass) {
            petClass = kNoPetSection;
        }
        if (stat >= 0 && petClass != kNoPetSection) {
            const auto pet = petLineStats_.find(parsed.key);
            stat = pet == petLineStats_.end() ? -1 : pet->second;
        }
        if (stat < 0 || !parsed.hasRange || parsed.values.size() != 1 ||
            parsed.high <= parsed.low) {
            continue;
        }
        const double points = stats_[stat].points;
        if (points <= 0.0) {
            continue;
        }
        double position = (parsed.values[0] - parsed.low) / (parsed.high - parsed.low);
        position = std::min(1.0, std::max(0.0, position));
        weighted += position * points;
        totalPoints += points;
        ++result.rolledStats;
    }
    if (totalPoints > 0.0) {
        result.hasValue = true;
        result.value = weighted / totalPoints;
    }
    return result;
}

int GradeRank(const std::string& grade) {
    static const char* const kOrder[] = {"F", "D", "C", "B", "A", "S", "S+", "S++"};
    for (int index = 0; index < 8; ++index) {
        if (grade == kOrder[index]) {
            return index;
        }
    }
    return -1;
}

bool GradeTable::ShouldHide(const std::string& grade, const std::string& rarity) const {
    if (!filterEnabled_) {
        return false;
    }
    const auto threshold = hideBelow_.find(rarity);
    if (threshold == hideBelow_.end()) {
        return false;
    }
    const int have = GradeRank(grade);
    const int need = GradeRank(threshold->second);
    return have >= 0 && need >= 0 && have < need;
}

std::string GradeTable::Label(const std::string& grade, const RollQualityResult& quality) {
    constexpr std::size_t kMaxLength = 7;
    if (!quality.hasValue) {
        return grade.substr(0, kMaxLength);
    }
    // Python's round() is banker's rounding; std::nearbyint uses the current
    // rounding mode, which defaults to round-half-to-even as well.
    const int percent = static_cast<int>(std::nearbyint(quality.value * 100.0));
    std::string label = grade + " " + std::to_string(percent) + "%";
    if (label.size() > kMaxLength) {
        label = grade + std::to_string(percent) + "%";
    }
    return label.substr(0, kMaxLength);
}

}  // namespace gg::core
