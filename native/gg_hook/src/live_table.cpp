#include "live_table.h"

#include <windows.h>

#include <atomic>
#include <string>
#include <thread>

#include "hook_log.h"
#include "reporter.h"

namespace gg {
namespace {

std::shared_ptr<const core::GradeTable> g_table;  // accessed via atomic_load/store
std::atomic<bool> g_started{false};

std::wstring TablePath() {
    wchar_t buffer[MAX_PATH] = {};
    const DWORD length = GetEnvironmentVariableW(L"LOCALAPPDATA", buffer, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return L"grade_table.txt";
    }
    return std::wstring(buffer) + L"\\GrimGleaner\\live\\grade_table.txt";
}

bool ModifiedTime(const std::wstring& path, ULONGLONG* stamp) {
    WIN32_FILE_ATTRIBUTE_DATA data;
    if (!GetFileAttributesExW(path.c_str(), GetFileExInfoStandard, &data)) {
        return false;
    }
    *stamp = (static_cast<ULONGLONG>(data.ftLastWriteTime.dwHighDateTime) << 32) |
             data.ftLastWriteTime.dwLowDateTime;
    return true;
}

bool ReadWholeFile(const std::wstring& path, std::string* contents) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    LARGE_INTEGER size{};
    bool ok = GetFileSizeEx(file, &size) && size.QuadPart < (64LL << 20);
    if (ok) {
        contents->assign(static_cast<std::size_t>(size.QuadPart), '\0');
        DWORD read = 0;
        ok = contents->empty() ||
             (ReadFile(file, contents->data(), static_cast<DWORD>(contents->size()), &read,
                       nullptr) &&
              read == contents->size());
    }
    CloseHandle(file);
    return ok;
}

void LoadTable(const std::wstring& path) {
    std::string text;
    if (!ReadWholeFile(path, &text)) {
        return;
    }
    auto table = std::make_shared<core::GradeTable>();
    std::string error;
    if (!table->Load(text, &error)) {
        Log("grade table rejected: " + error);
        Report("GG1\ttable\t-\terror\t" + error);
        return;
    }
    std::atomic_store(&g_table, std::shared_ptr<const core::GradeTable>(table));
    Log("grade table loaded: " + table->id());
    Report("GG1\ttable\t" + table->id() + "\tok\tfilter=" +
           (table->filterEnabled() ? "1" : "0") + " inject=" +
           (table->injectLabel() ? "1" : "0") + " detail=" +
           (table->detailPass() ? "1" : "0"));
}

void WatcherMain() {
    const std::wstring path = TablePath();
    ULONGLONG loadedStamp = 0;
    for (;;) {
        ULONGLONG stamp = 0;
        if (ModifiedTime(path, &stamp) && stamp != loadedStamp) {
            // Gleaner writes atomically (temp file + rename), so a changed
            // stamp means a complete file.
            loadedStamp = stamp;
            try {
                LoadTable(path);
            } catch (...) {
                Log("grade table: unexpected exception while loading");
            }
        }
        Sleep(2000);
    }
}

}  // namespace

std::shared_ptr<const core::GradeTable> CurrentTable() {
    return std::atomic_load(&g_table);
}

void StartTableWatcher() {
    if (g_started.exchange(true)) {
        return;
    }
    std::thread(WatcherMain).detach();
}

}  // namespace gg
