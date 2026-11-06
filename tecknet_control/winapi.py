"""Win32 declarations shared by the input engine, device detection and actions."""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

WH_MOUSE_LL = 14
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_INPUT = 0x00FF
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_MOUSEHWHEEL = 0x020E
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_APP = 0x8000
HWND_MESSAGE = -3

LLMHF_INJECTED = 0x01

RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEMOUSE = 0
RI_MOUSE_BUTTON_4_DOWN = 0x0040
RI_MOUSE_BUTTON_4_UP = 0x0080
RI_MOUSE_BUTTON_5_DOWN = 0x0100
RI_MOUSE_BUTTON_5_UP = 0x0200
RI_MOUSE_HWHEEL = 0x0800

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
WHEEL_DELTA = 120

# Marks input sent by this app, so it is easy to recognise in a debugger.
INJECT_TAG = 0x54434B4E  # "TCKN"


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class _RAWMOUSEBUTTONS(ctypes.Structure):
    _fields_ = [("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT)]


class _RAWMOUSEUNION(ctypes.Union):
    _anonymous_ = ("s",)
    _fields_ = [("ulButtons", wintypes.ULONG), ("s", _RAWMOUSEBUTTONS)]


class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("u", _RAWMOUSEUNION),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", wintypes.HANDLE), ("dwType", wintypes.DWORD)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


def _declare(function, argtypes, restype):
    function.argtypes = argtypes
    function.restype = restype


_declare(kernel32.GetModuleHandleW, [wintypes.LPCWSTR], wintypes.HMODULE)
_declare(user32.SetWindowsHookExW, [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD], wintypes.HHOOK)
_declare(user32.CallNextHookEx, [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM], LRESULT)
_declare(user32.UnhookWindowsHookEx, [wintypes.HHOOK], wintypes.BOOL)
_declare(user32.SendInput, [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT)
_declare(user32.GetRawInputData, [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT), wintypes.UINT], wintypes.UINT)
_declare(user32.GetRawInputDeviceInfoW, [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT)], wintypes.UINT)
_declare(user32.GetRawInputDeviceList, [ctypes.POINTER(RAWINPUTDEVICELIST), ctypes.POINTER(wintypes.UINT), wintypes.UINT], wintypes.UINT)
_declare(user32.RegisterRawInputDevices, [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT], wintypes.BOOL)
_declare(user32.RegisterClassW, [ctypes.POINTER(WNDCLASSW)], wintypes.ATOM)
_declare(user32.CreateWindowExW, [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
], wintypes.HWND)
_declare(user32.DestroyWindow, [wintypes.HWND], wintypes.BOOL)
_declare(user32.DefWindowProcW, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], LRESULT)
_declare(user32.SetTimer, [wintypes.HWND, ULONG_PTR, wintypes.UINT, wintypes.LPVOID], ULONG_PTR)
_declare(user32.KillTimer, [wintypes.HWND, ULONG_PTR], wintypes.BOOL)
_declare(user32.PostMessageW, [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL)
_declare(user32.GetMessageW, [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT], wintypes.BOOL)
_declare(user32.TranslateMessage, [ctypes.POINTER(wintypes.MSG)], wintypes.BOOL)
_declare(user32.DispatchMessageW, [ctypes.POINTER(wintypes.MSG)], LRESULT)
_declare(user32.PostQuitMessage, [ctypes.c_int], None)
_declare(user32.GetCursorPos, [ctypes.POINTER(POINT)], wintypes.BOOL)


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SPI_GETMOUSESPEED = 0x0070
SPI_SETMOUSESPEED = 0x0071
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_declare(user32.GetForegroundWindow, [], wintypes.HWND)
_declare(user32.GetWindowThreadProcessId, [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD)
_declare(user32.IsWindowVisible, [wintypes.HWND], wintypes.BOOL)
_declare(user32.GetWindowTextLengthW, [wintypes.HWND], ctypes.c_int)
_declare(user32.EnumWindows, [WNDENUMPROC, wintypes.LPARAM], wintypes.BOOL)
_declare(user32.SystemParametersInfoW, [wintypes.UINT, wintypes.UINT, wintypes.LPVOID, wintypes.UINT], wintypes.BOOL)
_declare(kernel32.OpenProcess, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
_declare(kernel32.QueryFullProcessImageNameW, [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
_declare(kernel32.CloseHandle, [wintypes.HANDLE], wintypes.BOOL)


def window_program(window):
    """File name, in lower case, of the program that owns a window ("" if unknown)."""
    if not window:
        return ""
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value.rsplit("\\", 1)[-1].lower()
    finally:
        kernel32.CloseHandle(process)


def open_window_programs():
    """Programs that have a visible window with a title, sorted by name."""
    found = set()

    def visit(window, _):
        if user32.IsWindowVisible(window) and user32.GetWindowTextLengthW(window) > 0:
            name = window_program(window)
            if name.endswith(".exe"):
                found.add(name)
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)
    return sorted(found)


def pointer_speed():
    speed = ctypes.c_int(10)
    user32.SystemParametersInfoW(SPI_GETMOUSESPEED, 0, ctypes.byref(speed), 0)
    return speed.value


def set_pointer_speed(speed):
    """Change the pointer speed (1-20) for this session only; never saved."""
    user32.SystemParametersInfoW(SPI_SETMOUSESPEED, 0, ctypes.c_void_p(max(1, min(20, speed))), 0)


def raw_device_name(handle):
    """Return the Raw Input device path in upper case, or "" when unknown."""
    if not handle:
        return ""
    size = wintypes.UINT(0)
    user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, None, ctypes.byref(size))
    if not size.value:
        return ""
    buffer = ctypes.create_unicode_buffer(size.value + 1)
    if user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, buffer, ctypes.byref(size)) == 0xFFFFFFFF:
        return ""
    return buffer.value.upper()


def raw_mouse_device_names():
    """Device paths of the mice currently known to Raw Input."""
    count = wintypes.UINT(0)
    item_size = ctypes.sizeof(RAWINPUTDEVICELIST)
    if user32.GetRawInputDeviceList(None, ctypes.byref(count), item_size) == 0xFFFFFFFF:
        return []
    devices = (RAWINPUTDEVICELIST * count.value)()
    found = user32.GetRawInputDeviceList(devices, ctypes.byref(count), item_size)
    if found == 0xFFFFFFFF:
        return []
    return [raw_device_name(d.hDevice) for d in devices[:found] if d.dwType == RIM_TYPEMOUSE]
