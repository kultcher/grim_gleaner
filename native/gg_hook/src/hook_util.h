#pragma once
#include <string>

namespace gg {
// Attach a Detours hook, updating every other thread of the process.
// *original holds the target on entry and the trampoline on success.
bool AttachHook(void** original, void* replacement, std::string* error);
}  // namespace gg
