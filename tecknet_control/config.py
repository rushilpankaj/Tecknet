"""Settings: where they live, their defaults and how they are checked.

Settings stay in %APPDATA%\\TecknetControl\\settings.json. Files from v1.6
are converted on load. Unknown or invalid values fall back to the defaults,
so a damaged file never stops the app.
"""

import json
import logging
import os
from pathlib import Path

from . import actions
from .device_ids import TECKNET_IDS
from .engine import EngineConfig

log = logging.getLogger(__name__)

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "TecknetControl"
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "tecknet_control.log"

THEMES = ("System", "Light", "Dark")
WHEEL_TARGETS = ("TECKNET mouse only", "All devices")
DOUBLE_CLICK_RANGE = (150, 600)
SETTINGS_VERSION = 3

# Side-button slots: button 1 (Back) and 2 (Forward), click and double click.
SLOTS = ("1_click", "1_double", "2_click", "2_double")
CUSTOM_ACTIONS = [actions.OPEN_PROGRAM, actions.SHORTCUT]
SLOT_ACTIONS = {
    "click": [actions.NORMAL_CLICK] + actions.BUTTON_ACTIONS + CUSTOM_ACTIONS,
    "double": actions.BUTTON_ACTIONS + CUSTOM_ACTIONS,
}
DEFAULT_SLOT_ACTIONS = {
    "1_click": actions.NORMAL_CLICK,
    "1_double": "Calculator",
    "2_click": actions.NORMAL_CLICK,
    "2_double": "Spotify",
}

DEFAULTS = {
    "settings_version": SETTINGS_VERSION,
    "enable_controls": True,
    "wheel_preset": "Volume",
    "invert_wheel": False,
    "wheel_target": WHEEL_TARGETS[0],
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
    return slot.split("_")[1]


def _from_v16(data):
    """v1.6 kept the side buttons in flat keys; turn them into slots."""
    slots = {}
    for button in (1, 2):
        double = empty_slot(data.get(f"xbutton{button}_double", DEFAULT_SLOT_ACTIONS[f"{button}_double"]))
        double["program"] = data.get(f"custom_xbutton{button}", "")
        double["program_name"] = data.get(f"custom_xbutton{button}_name", "")
        slots[f"{button}_double"] = double
        slots[f"{button}_click"] = empty_slot(data.get(f"xbutton{button}_single", actions.NORMAL_CLICK))
    return slots


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
    if settings["wheel_target"] not in WHEEL_TARGETS:
        settings["wheel_target"] = DEFAULTS["wheel_target"]
    if settings["theme"] not in THEMES:
        settings["theme"] = DEFAULTS["theme"]
    if not settings["device_ids"]:
        settings["device_ids"] = list(TECKNET_IDS)
    low, high = DOUBLE_CLICK_RANGE
    settings["double_click_ms"] = max(low, min(high, settings["double_click_ms"]))

    raw_slots = data.get("buttons")
    if not isinstance(raw_slots, dict):
        raw_slots = _from_v16(data)
    settings["buttons"] = {slot: _clean_slot(slot, raw_slots.get(slot)) for slot in SLOTS}
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
    if name == actions.DO_NOTHING and slot_kind(slot) == "double":
        return None
    if name == actions.OPEN_PROGRAM:
        if not actions.valid_program(data["program"]):
            return None
        return actions.Binding(name, program=data["program"])
    if name == actions.SHORTCUT:
        return actions.Binding(name, keys=tuple(data["keys"]))
    return actions.Binding(name)


def engine_config(settings):
    pair = actions.WHEEL_PRESETS[settings["wheel_preset"]]
    return EngineConfig(
        enabled=settings["enable_controls"],
        wheel=None if pair is None else tuple(actions.Binding(name) for name in pair),
        invert_wheel=settings["invert_wheel"],
        only_target_devices=settings["wheel_target"] == WHEEL_TARGETS[0],
        target_ids=frozenset(settings["device_ids"]),
        single_click={b: slot_binding(settings, f"{b}_click") for b in (1, 2)},
        double_click={b: slot_binding(settings, f"{b}_double") for b in (1, 2)},
        double_click_ms=settings["double_click_ms"],
    )
