#pragma once
#include <string>

namespace gg {
// Loopback UDP port the Grim Gleaner listener binds. Keep in sync with
// gd_affix_relevance/live/protocol.py.
inline constexpr unsigned short kReporterPort = 47817;

// Queue one protocol line for delivery. Safe to call from the game thread:
// it only takes a short lock and never blocks on I/O. Drops messages if the
// queue backs up.
void Report(std::string line);

void StartReporter();
void StopReporter();
}  // namespace gg
