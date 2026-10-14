"""Inject the gg_hook DLL into a running 64-bit Grim Dawn (Windows only).

Classic LoadLibraryW injection: write the DLL path into the game process and
start a remote thread at kernel32!LoadLibraryW. The DLL is copied to a
per-build file under %LOCALAPPDATA%\\GrimGleaner\\hook first, so rebuilding it
is not blocked by the copy the game holds open.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

GAME_EXECUTABLE = "grim dawn.exe"
HOOK_MODULE_PREFIX = "gg_hook"


class InjectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GameProcess:
    pid: int
    executable: Path


def staged_dll_path(dll: Path, staging_root: Path | None = None) -> Path:
    """Content-addressed copy location, so each build gets its own file."""

    digest = hashlib.sha256(Path(dll).read_bytes()).hexdigest()[:12]
    root = staging_root or _default_staging_root()
    return root / f"{HOOK_MODULE_PREFIX}-{digest}.dll"


def _default_staging_root() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "GrimGleaner" / "hook"


def require_windows_x64() -> None:
    if sys.platform != "win32":
        raise InjectionError("Injection is only supported on Windows.")
    if struct.calcsize("P") != 8:
        raise InjectionError("Use 64-bit Python: Grim Dawn is a 64-bit process.")


# --- Win32 plumbing --------------------------------------------------------

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_INJECT_ACCESS = 0x0002 | 0x0400 | 0x0008 | 0x0010 | 0x0020  # create thread, query, vm op/read/write
MEM_COMMIT_RESERVE = 0x3000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
WAIT_OBJECT_0 = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def _kernel32():
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    k32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    k32.Module32FirstW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    k32.Module32NextW.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    k32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    )
    k32.VirtualAllocEx.argtypes = (
        wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD
    )
    k32.VirtualAllocEx.restype = wintypes.LPVOID
    k32.VirtualFreeEx.argtypes = (wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD)
    k32.WriteProcessMemory.argtypes = (
        wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    )
    k32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    k32.GetModuleHandleW.restype = wintypes.HMODULE
    k32.GetProcAddress.argtypes = (wintypes.HMODULE, wintypes.LPCSTR)
    k32.GetProcAddress.restype = wintypes.LPVOID
    k32.CreateRemoteThread.argtypes = (
        wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.LPVOID,
        wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
    )
    k32.CreateRemoteThread.restype = wintypes.HANDLE
    k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.WaitForSingleObject.restype = wintypes.DWORD
    k32.GetExitCodeThread.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    return k32


def _last_error(action: str) -> InjectionError:
    code = ctypes.get_last_error()
    return InjectionError(f"{action} failed: {ctypes.FormatError(code).strip()} ({code})")


def _snapshot_structs():
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
            ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
            ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
            ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260),
        ]

    return PROCESSENTRY32W, MODULEENTRY32W


def find_game_processes() -> list[GameProcess]:
    require_windows_x64()
    k32 = _kernel32()
    PROCESSENTRY32W, _ = _snapshot_structs()
    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot in (None, INVALID_HANDLE_VALUE):
        raise _last_error("Listing processes")
    processes: list[GameProcess] = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        more = k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szExeFile.casefold() == GAME_EXECUTABLE:
                processes.append(
                    GameProcess(entry.th32ProcessID, _process_image(k32, entry.th32ProcessID))
                )
            more = k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snapshot)
    return processes


def _process_image(k32, pid: int) -> Path:
    from ctypes import wintypes

    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise _last_error(f"Opening Grim Dawn (pid {pid})")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise _last_error("Reading the Grim Dawn executable path")
        return Path(buffer.value)
    finally:
        k32.CloseHandle(handle)


def loaded_hook_modules(pid: int) -> list[str]:
    require_windows_x64()
    k32 = _kernel32()
    _, MODULEENTRY32W = _snapshot_structs()
    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot in (None, INVALID_HANDLE_VALUE):
        raise _last_error(f"Listing modules of pid {pid}")
    names: list[str] = []
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        more = k32.Module32FirstW(snapshot, ctypes.byref(entry))
        while more:
            if entry.szModule.casefold().startswith(HOOK_MODULE_PREFIX):
                names.append(entry.szModule)
            more = k32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snapshot)
    return names


def inject(pid: int, dll: Path, *, staging_root: Path | None = None) -> Path:
    """Copy *dll* to its staged location and load it into *pid*."""

    require_windows_x64()
    from ctypes import wintypes

    source = Path(dll).resolve()
    if not source.is_file():
        raise InjectionError(f"Hook DLL not found: {source}")
    staged = staged_dll_path(source, staging_root)
    staged.parent.mkdir(parents=True, exist_ok=True)
    if not staged.exists():
        shutil.copy2(source, staged)

    k32 = _kernel32()
    path_bytes = (str(staged) + "\0").encode("utf-16-le")
    process = k32.OpenProcess(PROCESS_INJECT_ACCESS, False, pid)
    if not process:
        raise _last_error(f"Opening Grim Dawn (pid {pid}) for injection")
    remote = None
    try:
        remote = k32.VirtualAllocEx(process, None, len(path_bytes), MEM_COMMIT_RESERVE, PAGE_READWRITE)
        if not remote:
            raise _last_error("Allocating memory in Grim Dawn")
        written = ctypes.c_size_t(0)
        if not k32.WriteProcessMemory(process, remote, path_bytes, len(path_bytes), ctypes.byref(written)):
            raise _last_error("Writing the DLL path into Grim Dawn")
        # kernel32 is mapped at the same address in every process of a session.
        load_library = k32.GetProcAddress(k32.GetModuleHandleW("kernel32.dll"), b"LoadLibraryW")
        thread = k32.CreateRemoteThread(process, None, 0, load_library, remote, 0, None)
        if not thread:
            raise _last_error("Starting the loader thread in Grim Dawn")
        try:
            if k32.WaitForSingleObject(thread, 15000) != WAIT_OBJECT_0:
                raise InjectionError("Grim Dawn did not finish loading the DLL within 15s")
            exit_code = wintypes.DWORD(0)
            k32.GetExitCodeThread(thread, ctypes.byref(exit_code))
            if exit_code.value == 0:
                raise InjectionError(
                    "LoadLibraryW returned NULL inside Grim Dawn. Check that the DLL is "
                    "an x64 Release build and its dependencies (MSVC runtime) are installed."
                )
        finally:
            k32.CloseHandle(thread)
    finally:
        if remote:
            k32.VirtualFreeEx(process, remote, 0, MEM_RELEASE)
        k32.CloseHandle(process)
    return staged
