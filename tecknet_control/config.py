"""Settings: where they live, their defaults and how they are checked.

Settings stay in %APPDATA%\\TecknetControl\\settings.json. Files from v1.6
are converted on load. Unknown or invalid values fall back to the defaults,
so a damaged file never stops the app.
"""

import json
import logging
import os
import re
from pathlib import Path

from . import actions
from .device_ids import TECKNET_IDS
from .engine import GESTURES, PRECISION, EngineConfig

log = logging.getLogger(__name__)

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "TecknetControl"
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "tecknet_control.log"

THEMES = ("System", "Light", "Dark")
DOUBLE_CLICK_RANGE = (150, 600)
SETTINGS_VERSION = 4
MAX_APP_PROFILES = 20
_PROGRAM_NAME = re.compile(r"^[\w .()+&-]{1,80}\.exe$")

# Side-button slots: button 1 (Back) and 2 (Forward) click, double click and
# hold, and the four gesture directions (shared by both buttons).
GESTURE_DIRECTIONS = ("left", "right", "up", "down")
SLOTS = ("1_click", "1_double", "1_hold", "2_click", "2_double", "2_hold") + tuple(
    f"gesture_{direction}" for direction in GESTURE_DIRECTIONS
)
CUSTOM_ACTIONS = [actions.OPEN_PROGRAM, actions.SHORTCUT]
_WITHOUT_NOTHING = [a for a in actions.BUTTON_ACTIONS if a != actions.DO_NOTHING]
SLOT_ACTIONS = {
    "click": [actions.NORMAL_CLICK] + actions.BUTTON_ACTIONS + CUSTOM_ACTIONS,
    "double": actions.BUTTON_ACTIONS + CUSTOM_ACTIONS,
    "hold": [actions.DO_NOTHING, actions.HOLD_GESTURES, actions.HOLD_PRECISION] + _WITHOUT_NOTHING + CUSTOM_ACTIONS,
    "gesture": actions.BUTTON_ACTIONS + CUSTOM_ACTIONS,
}
DEFAULT_SLOT_ACTIONS = {
    "1_click": actions.NORMAL_CLICK,
    "1_double": "Calculator",
    "1_hold": actions.DO_NOTHING,
    "2_click": actions.NORMAL_CLICK,
    "2_double": "Spotify",
    "2_hold": actions.DO_NOTHING,
    "gesture_left": "Previous Track",
    "gesture_right": "Next Track",
    "gesture_up": "Maximize Window",
    "gesture_down": "Minimize Window",
}
# Repeated when the side wheel is turned quickly (see engine.ACCELERATION).
ACCELERATED_ACTIONS = ("Volume Down", "Volume Up")

DEFAULTS = {
    "settings_version": SETTINGS_VERSION,
    "enable_controls": True,
    "wheel_preset": "Volume",
    "wheel_acceleration": True,
    "invert_wheel": False,
    "device_ids": list(TECKNET_IDS),
    "double_click_ms": 280,
    "start_with_windows": False,
    "minimize_to_tray": True,
    "low_battery_alert": True,
    "theme": "System",
}


def empty_slot(action):
    return {"action": action, "program": "", "program_name": "", "keys": [], "keys_label": ""}


def slot_kind(slot):
    """"click", "double", "hold" or "gesture"."""
    return "gesture" if slot.startswith("gesture_") else slot.split("_")[1]


def _clean_profiles(raw):
    """[{"app": "chrome.exe", "wheel": "Navigate Tabs"}, ...]: one per app."""
    profiles, seen = [], set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        app = item.get("app")
        wheel = item.get("wheel")
        if not isinstance(app, str) or not _PROGRAM_NAME.match(app.lower()) or wheel not in actions.WHEEL_PRESETS:
            continue
        if app.lower() not in seen and len(profiles) < MAX_APP_PROFILES:
            seen.add(app.lower())
            profiles.append({"app": app.lower(), "wheel": wheel})
    return profiles


def _clean_slot(slot, raw):
    clean = empty_slot(DEFAULT_SLOT_ACTIONS[slot])
    if not isinstance(raw, dict):
        return clean
    action = raw.get("action")
    if action not in SLOT_ACTIONS[slot_kind(slot)]:
        return clean
    clean["action"] = action
    if action == actions.OPEN_PROGRAM:
        program = raw.get("program")
        if isinstance(program, str) and program:
            clean["program"] = program
            name = raw.get("program_name")
            clean["program_name"] = name if isinstance(name, str) and name else Path(program).stem
    elif action == actions.SHORTCUT:
        keys = raw.get("keys")
        if actions.valid_shortcut(keys):
            clean["keys"] = list(keys)
            label = raw.get("keys_label")
            clean["keys_label"] = label if isinstance(label, str) else ""
        else:
            return empty_slot(DEFAULT_SLOT_ACTIONS[slot])
    return clean


def _clean(data):
    settings = DEFAULTS.copy()
    for key, default in DEFAULTS.items():
        value = data.get(key, default)
        if isinstance(default, bool):
            settings[key] = value if isinstance(value, bool) else default
        elif isinstance(default, int):
            settings[key] = value if isinstance(value, int) and not isinstance(value, bool) else default
        elif isinstance(default, list):
            settings[key] = [v for v in value if isinstance(v, str) and v][:16] if isinstance(value, list) else default
        else:
            settings[key] = value if isinstance(value, str) else default

    if settings["wheel_preset"] not in actions.WHEEL_PRESETS:
        settings["wheel_preset"] = DEFAULTS["wheel_preset"]
    if settings["theme"] not in THEMES:
        settings["theme"] = DEFAULTS["theme"]
    if not settings["device_ids"]:
        settings["device_ids"] = list(TECKNET_IDS)
    low, high = DOUBLE_CLICK_RANGE
    settings["double_click_ms"] = max(low, min(high, settings["double_click_ms"]))

    raw_slots = data.get("buttons") if isinstance(data.get("buttons"), dict) else {}
    settings["buttons"] = {slot: _clean_slot(slot, raw_slots.get(slot)) for slot in SLOTS}
    settings["app_profiles"] = _clean_profiles(data.get("app_profiles"))
    settings["settings_version"] = SETTINGS_VERSION
    return settings


def load_settings():
    data = {}
    if SETTINGS_FILE.exists():
        try:
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            log.warning("settings.json could not be read; using defaults")
    return _clean(data)


def save_settings(settings):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(_clean(settings), indent=2), encoding="utf-8")
    os.replace(temporary, SETTINGS_FILE)


def slot_binding(settings, slot):
    """The action a slot runs, or None for "normal click" / "no double click"."""
    data = settings["buttons"][slot]
    name = data["action"]
    if name == actions.NORMAL_CLICK:
        return None
    if name == actions.DO_NOTHING and slot_kind(slot) != "click":
        return None  # a click set to Do Nothing still blocks the click
    if name == actions.HOLD_GESTURES:
        return GESTURES
    if name == actions.HOLD_PRECISION:
        return PRECISION
    if name == actions.OPEN_PROGRAM:
        if not actions.valid_program(data["program"]):
            return None
        return actions.Binding(name, program=data["program"])
    if name == actions.SHORTCUT:
        return actions.Binding(name, keys=tuple(data["keys"]))
    return actions.Binding(name)


def wheel_bindings(preset):
    pair = actions.WHEEL_PRESETS[preset]
    return None if pair is None else tuple(actions.Binding(name) for name in pair)


def engine_config(settings):
    accelerated = ACCELERATED_ACTIONS if settings["wheel_acceleration"] else ()
    return EngineConfig(
        enabled=settings["enable_controls"],
        wheel=wheel_bindings(settings["wheel_preset"]),
        wheel_by_app={p["app"]: wheel_bindings(p["wheel"]) for p in settings["app_profiles"]},
        invert_wheel=settings["invert_wheel"],
        accelerated=frozenset(actions.Binding(name) for name in accelerated),
        hold={b: slot_binding(settings, f"{b}_hold") for b in (1, 2)},
        gestures={d: slot_binding(settings, f"gesture_{d}") for d in GESTURE_DIRECTIONS},
        target_ids=frozenset(settings["device_ids"]),
        single_click={b: slot_binding(settings, f"{b}_click") for b in (1, 2)},
        double_click={b: slot_binding(settings, f"{b}_double") for b in (1, 2)},
        double_click_ms=settings["double_click_ms"],
    )
