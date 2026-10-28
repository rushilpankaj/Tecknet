"""What the side wheel and side buttons can do, and how it is sent to Windows.

An action is stored as a Binding: its name, plus the program for "Open app"
or the keys for "Keyboard shortcut". The names are the values kept in
settings.json (as in v1.6), so old settings keep working.

To add an action: add a line to KEY_ACTIONS (a key combination) or
LAUNCH_ACTIONS (a program or URI), then add its name to BUTTON_ACTIONS or to
a WHEEL_PRESETS pair.
"""

import ctypes
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from . import winapi

log = logging.getLogger(__name__)

VK_TAB = 0x09
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_C = 0x43
VK_D = 0x44
VK_S = 0x53
VK_V = 0x56
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_BROWSER_BACK = 0xA6
VK_BROWSER_FORWARD = 0xA7
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

MODIFIER_KEYS = {VK_CONTROL: "Ctrl", VK_SHIFT: "Shift", VK_MENU: "Alt", VK_LWIN: "Win"}

# Keys Windows needs to be told are "extended" (arrows, navigation, media...).
_EXTENDED_KEYS = {
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x6F, 0x90,
    VK_LWIN, VK_RWIN, VK_BROWSER_BACK, VK_BROWSER_FORWARD, VK_VOLUME_MUTE,
    VK_VOLUME_DOWN, VK_VOLUME_UP, VK_MEDIA_NEXT_TRACK, VK_MEDIA_PREV_TRACK,
    VK_MEDIA_PLAY_PAUSE,
}

# Key combinations: modifiers first, the main key last.
KEY_ACTIONS = {
    "Back": (VK_BROWSER_BACK,),
    "Forward": (VK_BROWSER_FORWARD,),
    "Volume Down": (VK_VOLUME_DOWN,),
    "Volume Up": (VK_VOLUME_UP,),
    "Mute": (VK_VOLUME_MUTE,),
    "Play / Pause": (VK_MEDIA_PLAY_PAUSE,),
    "Previous Track": (VK_MEDIA_PREV_TRACK,),
    "Next Track": (VK_MEDIA_NEXT_TRACK,),
    "Previous Tab": (VK_CONTROL, VK_SHIFT, VK_TAB),
    "Next Tab": (VK_CONTROL, VK_TAB),
    "Previous Desktop": (VK_CONTROL, VK_LWIN, VK_LEFT),
    "Next Desktop": (VK_CONTROL, VK_LWIN, VK_RIGHT),
    "Task View": (VK_LWIN, VK_TAB),
    "Show Desktop": (VK_LWIN, VK_D),
    "Screenshot": (VK_LWIN, VK_SHIFT, VK_S),
    "Alt + Tab": (VK_MENU, VK_TAB),
    "Copy": (VK_CONTROL, VK_C),
    "Paste": (VK_CONTROL, VK_V),
}

# Ctrl + mouse wheel works in browsers, PDF readers, Office and most programs.
ZOOM_ACTIONS = {"Zoom Out": -winapi.WHEEL_DELTA, "Zoom In": winapi.WHEEL_DELTA}

LAUNCH_ACTIONS = {
    "Calculator": "calc.exe",
    "Spotify": "spotify:",
    "File Explorer": "explorer.exe",
}

NORMAL_CLICK = "Normal"  # single click: the button's own Back / Forward
DO_NOTHING = "Do Nothing"
OPEN_PROGRAM = "Open Program..."
SHORTCUT = "Keyboard Shortcut"

# Side wheel: (tilt left, tilt right). None means the wheel keeps its normal
# horizontal scroll and the app does not touch it.
WHEEL_PRESETS = {
    "Volume": ("Volume Down", "Volume Up"),
    "Horizontal Scroll": None,
    "Navigate Tabs": ("Previous Tab", "Next Tab"),
    "Media Tracks": ("Previous Track", "Next Track"),
    "Zoom": ("Zoom Out", "Zoom In"),
    "Virtual Desktops": ("Previous Desktop", "Next Desktop"),
}

# Choices for a side-button click or double click, in menu order.
BUTTON_ACTIONS = [
    "Back", "Forward", "Play / Pause", "Next Track", "Previous Track", "Mute",
    "Task View", "Show Desktop", "Screenshot", "Alt + Tab", "Copy", "Paste",
    "Calculator", "File Explorer", "Spotify", DO_NOTHING,
]

ALLOWED_PROGRAM_SUFFIXES = {".exe", ".lnk"}
MAX_SHORTCUT_KEYS = 5


@dataclass(frozen=True)
class Binding:
    name: str
    program: str = ""
    keys: tuple = ()


def valid_program(path):
    """A program chosen by the user: an existing, absolute local .exe or .lnk."""
    if not path or not isinstance(path, str):
        return False
    target = Path(path)
    if not target.is_absolute() or target.suffix.lower() not in ALLOWED_PROGRAM_SUFFIXES:
        return False
    if str(target).startswith("\\\\"):
        return False  # network paths are refused
    return target.is_file()


def valid_shortcut(keys):
    """1-5 virtual-key codes with exactly one key that is not a modifier, last."""
    if not isinstance(keys, (list, tuple)) or not 1 <= len(keys) <= MAX_SHORTCUT_KEYS:
        return False
    if not all(isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= 254 for k in keys):
        return False
    *modifiers, main = keys
    return main not in MODIFIER_KEYS and all(k in MODIFIER_KEYS for k in modifiers)


def _key_input(vk, up):
    flags = winapi.KEYEVENTF_KEYUP if up else 0
    if vk in _EXTENDED_KEYS:
        flags |= winapi.KEYEVENTF_EXTENDEDKEY
    item = winapi.INPUT(type=winapi.INPUT_KEYBOARD)
    item.ki = winapi.KEYBDINPUT(vk, 0, flags, 0, winapi.INJECT_TAG)
    return item


def _mouse_input(flags, data=0):
    item = winapi.INPUT(type=winapi.INPUT_MOUSE)
    item.mi = winapi.MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, winapi.INJECT_TAG)
    return item


def key_combo_inputs(keys):
    downs = [_key_input(vk, up=False) for vk in keys]
    ups = [_key_input(vk, up=True) for vk in reversed(keys)]
    return downs + ups


def zoom_inputs(delta):
    return [
        _key_input(VK_CONTROL, up=False),
        _mouse_input(winapi.MOUSEEVENTF_WHEEL, delta),
        _key_input(VK_CONTROL, up=True),
    ]


def _send(inputs):
    array = (winapi.INPUT * len(inputs))(*inputs)
    winapi.user32.SendInput(len(inputs), array, ctypes.sizeof(winapi.INPUT))


def send_horizontal_wheel(delta):
    """Re-send a horizontal scroll exactly as it was (used for other devices)."""
    _send([_mouse_input(winapi.MOUSEEVENTF_HWHEEL, delta)])


def send_side_click(button):
    """A normal Back (button 1) or Forward (button 2) click."""
    _send([
        _mouse_input(winapi.MOUSEEVENTF_XDOWN, button),
        _mouse_input(winapi.MOUSEEVENTF_XUP, button),
    ])


def _launch(target):
    def run():
        try:
            os.startfile(target)  # ShellExecute: no command line, no shell parsing
        except OSError as error:
            log.warning("Could not open program: %s", error.strerror)
    threading.Thread(target=run, daemon=True).start()


def run_action(binding):
    """Run one Binding. Unknown names, invalid programs and invalid keys do nothing."""
    name = binding.name
    if name in KEY_ACTIONS:
        _send(key_combo_inputs(KEY_ACTIONS[name]))
    elif name in ZOOM_ACTIONS:
        _send(zoom_inputs(ZOOM_ACTIONS[name]))
    elif name in LAUNCH_ACTIONS:
        _launch(LAUNCH_ACTIONS[name])
    elif name == OPEN_PROGRAM:
        if valid_program(binding.program):
            _launch(binding.program)
        else:
            log.warning("Selected program is missing or not allowed")
    elif name == SHORTCUT:
        if valid_shortcut(binding.keys):
            _send(key_combo_inputs(binding.keys))
