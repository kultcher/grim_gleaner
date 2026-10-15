#pragma once
// The grade table written by Grim Gleaner
// (%LOCALAPPDATA%\GrimGleaner\live\grade_table.txt). A watcher thread polls
// its modification time and swaps in a freshly parsed copy; hooks read the
// current one without blocking each other.

#include <memory>

#include "stat_core.h"

namespace gg {

// Null until a table has loaded successfully.
std::shared_ptr<const core::GradeTable> CurrentTable();

// Load once now, then re-check every two seconds on a background thread.
void StartTableWatcher();

}  // namespace gg
