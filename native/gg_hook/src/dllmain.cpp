// Grim Gleaner hook DLL entry point.
//
// Injected into a running Grim Dawn. Installs the tooltip hook on a worker
// thread (never inside DllMain, which runs under the loader lock) and pins
// itself so it can never be unloaded while hooks point into it. To load a new
// build, restart the game.

#include <windows.h>

#include <string>

#include "hook_log.h"
#include "reporter.h"
#include "tooltip_hook.h"

namespace {

constexpr unsigned int kHookVersion = 3;

void PinSelf(HMODULE module) {
    HMODULE pinned = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                           GET_MODULE_HANDLE_EX_FLAG_PIN,
                       reinterpret_cast<LPCWSTR>(module), &pinned);
}

DWORD WINAPI InitThread(LPVOID) {
    gg::Log("gg_hook v" + std::to_string(kHookVersion) + " loaded");
    gg::StartReporter();

    // Injection normally happens into a fully started game, but allow for an
    // early injection while Game.dll is still loading.
    for (int attempt = 0; attempt < 60 && GetModuleHandleW(L"Game.dll") == nullptr;
         ++attempt) {
        Sleep(500);
    }

    std::string detail;
    const bool ok = gg::InstallTooltipHook(&detail);
    gg::Log(std::string(ok ? "install ok: " : "install failed: ") + detail);
    const std::string pid = std::to_string(GetCurrentProcessId());
    gg::Report("GG1\thello\t" + pid + "\t" + (ok ? "ok" : "error") + "\t" + detail);

    // Heartbeat so a listener started after injection still sees the hook.
    for (;;) {
        Sleep(5000);
        gg::Report("GG1\theartbeat\t" + pid + "\t" + (ok ? "ok" : "error") + "\t" +
                   std::to_string(gg::TooltipCallCount()));
    }
}

}  // namespace

extern "C" __declspec(dllexport) unsigned int GgHookVersion() {
    return kHookVersion;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        PinSelf(module);
        HANDLE thread = CreateThread(nullptr, 0, InitThread, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}
