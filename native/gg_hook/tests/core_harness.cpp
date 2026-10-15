// Test harness for stat_core: reads a grade table and a case file, prints one
// result line per case for tests/test_native_core.py to compare with Python.
//
// Case file (tab-separated):
//   key     <text>                    -> "key\t<line key>"
//   case    <base> <prefix> <suffix>  starts an item
//   l       <class> <text>            adds a tooltip line to it
//   end                               -> "item\t<grade>\t<score>\t<matched>\t
//                                         <total>\t<rarity>\t<rq or ->\t<label>\t<hide>"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "../src/stat_core.h"

namespace {
std::vector<std::string> SplitTabs(const std::string& line) {
    std::vector<std::string> parts;
    std::stringstream stream(line);
    std::string part;
    while (std::getline(stream, part, '\t')) parts.push_back(part);
    if (!line.empty() && line.back() == '\t') parts.emplace_back();
    return parts;
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "usage: core_harness <table> <cases>\n";
        return 2;
    }
    std::ifstream tableFile(argv[1], std::ios::binary);
    std::stringstream tableText;
    tableText << tableFile.rdbuf();
    gg::core::GradeTable table;
    std::string error;
    if (!table.Load(tableText.str(), &error)) {
        std::cerr << "load failed: " << error << "\n";
        return 1;
    }
    std::cout << "table\t" << table.id() << "\n";

    std::ifstream cases(argv[2], std::ios::binary);
    std::string line;
    std::vector<std::string> records;
    std::vector<gg::core::TooltipLine> lines;
    while (std::getline(cases, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto fields = SplitTabs(line);
        if (fields.empty()) continue;
        if (fields[0] == "key" && fields.size() >= 2) {
            std::cout << "key\t" << gg::core::LineKey(fields[1]) << "\n";
        } else if (fields[0] == "case") {
            records = {fields.size() > 1 ? fields[1] : "", fields.size() > 2 ? fields[2] : "",
                       fields.size() > 3 ? fields[3] : ""};
            lines.clear();
        } else if (fields[0] == "l" && fields.size() >= 3) {
            lines.push_back({std::stoi(fields[1]), fields[2]});
        } else if (fields[0] == "end") {
            const auto relevance = table.Score(records);
            const auto quality = table.RollQuality(lines);
            char score[64];
            std::snprintf(score, sizeof(score), "%.9f", relevance.score);
            char rq[64] = "-";
            if (quality.hasValue) std::snprintf(rq, sizeof(rq), "%.9f", quality.value);
            std::cout << "item\t" << relevance.grade << "\t" << score << "\t"
                      << relevance.matched << "\t" << relevance.total << "\t"
                      << relevance.rarity << "\t" << rq << "\t"
                      << gg::core::GradeTable::Label(relevance.grade, quality) << "\t"
                      << (table.ShouldHide(relevance.grade, relevance.rarity) ? 1 : 0) << "\n";
        }
    }
    return 0;
}
