"""Windows integration: one running copy, start with Windows, v1.6 clean-up.

No PowerShell and no shell commands: the registry is changed with winreg and
processes are inspected with documented Win32 calls.
"""

import ctypes
import logging
import re
import sys
import threading
import winreg
from ctypes import wintypes
from pathlib import Path

from .config import APP_DIR

log = logging.getLogger(__name__)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0

# The installer uses the same mutex name (AppMutex) to know the app is running.
MUTEX_NAME = "TecknetControlSingleInstance"
SHOW_EVENT = "TecknetControlShowWindow"
EXIT_EVENT = "TecknetControlExit"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "TecknetControl"

kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenEventW.restype = wintypes.HANDLE
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.WaitForMultipleObjects.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL, wintypes.DWORD]
kernel32.WaitForMultipleObjects.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


# --- one running copy ---------------------------------------------------------
class SingleInstance:
    def __init__(self):
        self._mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        self._show = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
        self._exit = kernel32.CreateEventW(None, False, False, EXIT_EVENT)

    def listen(self, on_show, on_exit):
        """Call on_show / on_exit (from a background thread) when signalled."""
        handles = (wintypes.HANDLE * 2)(self._show, self._exit)

        def wait():
            while True:
                result = kernel32.WaitForMultipleObjects(2, handles, False, INFINITE)
                if result == WAIT_OBJECT_0:
                    on_show()
                elif result == WAIT_OBJECT_0 + 1:
                    on_exit()
                    return
                else:
                    return

        threading.Thread(target=wait, name="instance", daemon=True).start()


def signal_running_instance(event_name):
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, event_name)
    if not handle:
        return False
    kernel32.SetEvent(handle)
    kernel32.CloseHandle(handle)
    return True


# --- start with Windows -------------------------------------------------------
def startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    launcher = Path(__file__).resolve().parent.parent / "TecknetControl.pyw"
    return f'"{interpreter}" "{launcher}" --minimized'


def startup_enabled():
    """The registry is the source of truth: the installer can also set it."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


def set_startup(enabled):
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError as error:
        log.warning("Could not change start with Windows: %s", error.strerror)
        return False


# --- v1.6 clean-up ------------------------------------------------------------
LEGACY_FILES = ("controls.enabled", "ahk.pid", "tecknet_controls.ahk")
LEGACY_SCRIPT = re.compile(r'[\\/]mouse_test(?:e)?\.ahk"?\s*$', re.IGNORECASE)

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_COMMAND_LINE_INFORMATION = 60


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
ntdll.NtQueryInformationProcess.restype = ctypes.c_long


def _processes_named(prefix):
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return []
    found = []
    try:
        entry = PROCESSENTRY32W(dwSize=ctypes.sizeof(PROCESSENTRY32W))
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower().startswith(prefix):
                found.append(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found


def _command_line(handle):
    buffer = ctypes.create_string_buffer(65536)
    length = wintypes.ULONG(0)
    status = ntdll.NtQueryInformationProcess(
        handle, PROCESS_COMMAND_LINE_INFORMATION, buffer, len(buffer), ctypes.byref(length)
    )
    if status != 0:
        return ""
    text = UNICODE_STRING.from_buffer(buffer)
    if not text.Buffer:
        return ""
    return ctypes.wstring_at(text.Buffer, text.Length // 2)


def is_tecknet_script(command_line, generated_script):
    """True only for the script v1.6 generated and the two old test scripts."""
    if generated_script.lower() in command_line.lower():
        return True
    return bool(LEGACY_SCRIPT.search(command_line))


def clean_up_v16():
    """Turn off and stop the AutoHotkey scripts used by v1.6 and earlier tests."""
    for name in LEGACY_FILES[:2]:
        try:
            (APP_DIR / name).unlink(missing_ok=True)  # without the flag the v1.6 hotkeys are inactive
        except OSError:
            pass
    generated = str(APP_DIR / "tecknet_controls.ahk")
    stopped = 0
    for pid in _processes_named("autohotkey"):
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE, False, pid)
        if not handle:
            continue
        try:
            if is_tecknet_script(_command_line(handle), generated):
                kernel32.TerminateProcess(handle, 0)
                stopped += 1
        finally:
            kernel32.CloseHandle(handle)
    if stopped:
        log.info("Stopped %d old AutoHotkey script(s)", stopped)
    try:
        (APP_DIR / LEGACY_FILES[2]).unlink(missing_ok=True)
    except OSError:
        pass
    return stopped
