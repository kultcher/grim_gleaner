#include "hook_util.h"

#include <windows.h>
#include <tlhelp32.h>

#include <detours.h>

#include <vector>

namespace gg {
namespace {
// Detours must be told about every thread that might be executing the bytes
// it is about to patch.
std::vector<HANDLE> UpdateAllOtherThreads() {
    std::vector<HANDLE> handles;
    const DWORD process = GetCurrentProcessId();
    const DWORD self = GetCurrentThreadId();
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE) {
        return handles;
    }
    THREADENTRY32 entry{};
    entry.dwSize = sizeof(entry);
    for (BOOL more = Thread32First(snapshot, &entry); more;
         more = Thread32Next(snapshot, &entry)) {
        if (entry.th32OwnerProcessID != process || entry.th32ThreadID == self) {
            continue;
        }
        HANDLE thread = OpenThread(
            THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_SET_CONTEXT, FALSE,
            entry.th32ThreadID);
        if (thread != nullptr) {
            DetourUpdateThread(thread);
            handles.push_back(thread);
        }
    }
    CloseHandle(snapshot);
    return handles;
}
}  // namespace

bool AttachHook(void** original, void* replacement, std::string* error) {
    LONG result = DetourTransactionBegin();
    std::vector<HANDLE> threads;
    if (result == NO_ERROR) {
        threads = UpdateAllOtherThreads();
        result = DetourAttach(original, replacement);
        if (result == NO_ERROR) {
            result = DetourTransactionCommit();
        } else {
            DetourTransactionAbort();
        }
    }
    for (HANDLE thread : threads) {
        CloseHandle(thread);
    }
    if (result != NO_ERROR) {
        *error = "Detours failed to attach (error " + std::to_string(result) + ")";
        return false;
    }
    return true;
}
}  // namespace gg
