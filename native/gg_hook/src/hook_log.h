#pragma once
#include <string>

namespace gg {
// Appends a line to %LOCALAPPDATA%\GrimGleaner\gg_hook.log. Never throws.
void Log(const std::string& message);
}  // namespace gg
