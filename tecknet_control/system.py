"""Windows integration: one running copy of the app, and start with Windows.

No PowerShell and no shell commands: the registry is changed with winreg.
"""

import ctypes
import logging
import sys
import threading
import winreg
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

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
