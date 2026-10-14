#include "hook_log.h"

#include <windows.h>

#include <cstdio>
#include <mutex>

namespace gg {
namespace {
std::mutex g_logMutex;

std::wstring LogPath() {
    wchar_t buffer[MAX_PATH] = {};
    DWORD length = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return L"gg_hook.log";
    }
    std::wstring folder = std::wstring(buffer) + L"\\GrimGleaner";
    CreateDirectoryW(folder.c_str(), nullptr);
    return folder + L"\\gg_hook.log";
}
}  // namespace

void Log(const std::string& message) {
    try {
        std::lock_guard<std::mutex> lock(g_logMutex);
        static const std::wstring path = LogPath();
        FILE* file = _wfopen(path.c_str(), L"ab");
        if (file == nullptr) {
            return;
        }
        SYSTEMTIME now;
        GetLocalTime(&now);
        std::fprintf(file, "%04u-%02u-%02u %02u:%02u:%02u.%03u %s\r\n",
                     now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute,
                     now.wSecond, now.wMilliseconds, message.c_str());
        std::fclose(file);
    } catch (...) {
    }
}
}  // namespace gg
