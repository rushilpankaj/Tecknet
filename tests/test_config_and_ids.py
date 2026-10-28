import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tecknet_control import actions, config, system
from tecknet_control.device_ids import device_id, transport

USB_MOUSE = r"\\?\HID#VID_25A7&PID_FA61&MI_01&COL01#7&75A1477&0&0000#{378DE44C-56EF-11D1-BC8C-00A0C91405DD}"
BT_MOUSE = r"\\?\HID#{00001812-0000-1000-8000-00805F9B34FB}_DEV_VID&0225A7_PID&FAA0_REV&0508_112233445566&COL01#9&1&0000#{378DE44C}"
TRACKPAD = r"\\?\HID#ELAN0527&COL01#5&1423B517&0&0000#{378DE44C-56EF-11D1-BC8C-00A0C91405DD}"


class DeviceIdTest(unittest.TestCase):
    def test_ids(self):
        self.assertEqual(device_id(USB_MOUSE), "25A7:FA61")
        self.assertEqual(device_id(BT_MOUSE), "25A7:FAA0")
        self.assertEqual(device_id(TRACKPAD), "ELAN0527")
        self.assertEqual(device_id(""), "")

    def test_transport(self):
        self.assertEqual(transport(USB_MOUSE), "usb")
        self.assertEqual(transport(BT_MOUSE), "bluetooth")
        self.assertEqual(transport(TRACKPAD), "other")


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.file = Path(self.folder.name) / "settings.json"
        patches = [
            mock.patch.object(config, "APP_DIR", Path(self.folder.name)),
            mock.patch.object(config, "SETTINGS_FILE", self.file),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.folder.cleanup)

    def test_v16_settings_are_converted(self):
        app = Path(self.folder.name) / "Tool.exe"
        app.write_bytes(b"MZ")
        self.file.write_text(json.dumps({
            "wheel_left": "Volume Down", "wheel_right": "Volume Up", "wheel_preset": "Zoom",
            "xbutton1_double": "Open Program...", "custom_xbutton1": str(app), "custom_xbutton1_name": "",
            "xbutton2_double": "Spotify", "custom_xbutton2": r"C:\old.lnk",
            "enable_controls": False, "theme": "Dark",
        }), encoding="utf-8")
        settings = config.load_settings()
        self.assertEqual(settings["wheel_preset"], "Zoom")
        slots = settings["buttons"]
        self.assertEqual(slots["1_double"]["program_name"], "Tool")
        self.assertEqual(slots["2_double"]["program"], "")  # leftover program dropped
        self.assertEqual(slots["1_click"]["action"], actions.NORMAL_CLICK)
        self.assertFalse(settings["enable_controls"])
        self.assertEqual(settings["theme"], "Dark")
        self.assertNotIn("wheel_left", settings)
        self.assertNotIn("xbutton1_double", settings)
        engine = config.engine_config(settings)
        self.assertEqual(engine.wheel, (actions.Binding("Zoom Out"), actions.Binding("Zoom In")))
        self.assertEqual(engine.double_click[1], actions.Binding("Open Program...", program=str(app)))
        self.assertEqual(engine.double_click[2], actions.Binding("Spotify"))
        self.assertEqual(engine.single_click, {1: None, 2: None})

    def test_invalid_values_fall_back(self):
        self.file.write_text(json.dumps({
            "wheel_preset": "Copy/Paste", "theme": 3, "double_click_ms": 5,
            "device_ids": "x", "invert_wheel": "yes",
            "buttons": {
                "1_double": {"action": "rm -rf"},
                "1_click": {"action": "Keyboard Shortcut", "keys": [17, 17]},
                "2_click": "x",
            },
        }), encoding="utf-8")
        settings = config.load_settings()
        self.assertEqual(settings["wheel_preset"], "Volume")
        self.assertEqual(settings["theme"], "System")
        self.assertEqual(settings["double_click_ms"], 150)
        self.assertEqual(settings["device_ids"], ["25A7:FA61", "25A7:FAA0"])
        self.assertFalse(settings["invert_wheel"])
        slots = settings["buttons"]
        self.assertEqual(slots["1_double"]["action"], "Calculator")
        self.assertEqual(slots["1_click"]["action"], actions.NORMAL_CLICK)
        self.assertEqual(slots["2_click"]["action"], actions.NORMAL_CLICK)

    def test_click_choices(self):
        settings = config.load_settings()
        settings["buttons"]["2_click"] = {"action": "Back"}
        settings["buttons"]["1_click"] = {"action": "Keyboard Shortcut", "keys": [17, 84], "keys_label": "Ctrl + T"}
        settings["buttons"]["2_double"] = {"action": actions.DO_NOTHING}
        config.save_settings(settings)
        engine = config.engine_config(config.load_settings())
        self.assertEqual(engine.single_click[2], actions.Binding("Back"))
        self.assertEqual(engine.single_click[1], actions.Binding("Keyboard Shortcut", keys=(17, 84)))
        self.assertIsNone(engine.double_click[2])

    def test_click_do_nothing_blocks_the_click(self):
        settings = config.load_settings()
        settings["buttons"]["1_click"] = {"action": actions.DO_NOTHING}
        self.assertEqual(config.slot_binding(settings, "1_click"), actions.Binding(actions.DO_NOTHING))

    def test_damaged_file_uses_defaults(self):
        self.file.write_text("{not json", encoding="utf-8")
        self.assertEqual(config.load_settings()["wheel_preset"], "Volume")

    def test_missing_program_is_not_run(self):
        settings = config.load_settings()
        settings["buttons"]["1_double"] = {"action": actions.OPEN_PROGRAM, "program": r"C:\missing\folder\app.exe"}
        self.assertIsNone(config.slot_binding(config._clean(settings), "1_double"))

    def test_save_and_load(self):
        settings = config.load_settings()
        settings["invert_wheel"] = True
        config.save_settings(settings)
        self.assertTrue(config.load_settings()["invert_wheel"])


class ProgramValidationTest(unittest.TestCase):
    def test_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / "a.exe"
            exe.write_bytes(b"MZ")
            script = Path(folder) / "a.bat"
            script.write_text("x")
            self.assertTrue(actions.valid_program(str(exe)))
            self.assertFalse(actions.valid_program(str(script)))
            self.assertFalse(actions.valid_program("a.exe"))
            self.assertFalse(actions.valid_program(r"\\server\share\a.exe"))
            self.assertFalse(actions.valid_program(str(Path(folder) / "missing.exe")))
            self.assertFalse(actions.valid_program(None))


class LegacyScriptTest(unittest.TestCase):
    generated = r"C:\Users\x\AppData\Roaming\TecknetControl\tecknet_controls.ahk"

    def test_only_tecknet_scripts_match(self):
        match = system.is_tecknet_script
        self.assertTrue(match(rf'"C:\AHK\AutoHotkey64.exe" {self.generated}', self.generated))
        self.assertTrue(match(r'"AutoHotkey64.exe" "C:\Docs\AutoHotkey\mouse_test.ahk"', self.generated))
        self.assertTrue(match(r'AutoHotkey64.exe C:\Docs\AutoHotkey\mouse_teste.ahk', self.generated))
        self.assertFalse(match(r'AutoHotkey64.exe "C:\Docs\my_mouse_test.ahk"', self.generated))
        self.assertFalse(match(r'AutoHotkey64.exe "C:\Docs\mouse_test.ahk.bak"', self.generated))
        self.assertFalse(match(r'AutoHotkey64.exe "C:\Docs\shortcuts.ahk"', self.generated))

    def test_reads_own_command_line(self):
        import ctypes
        handle = system.kernel32.OpenProcess(system.PROCESS_QUERY_LIMITED_INFORMATION, False, __import__("os").getpid())
        try:
            self.assertIn("python", system._command_line(handle).lower())
        finally:
            system.kernel32.CloseHandle(handle)


class KeyInputTest(unittest.TestCase):
    def test_combo_presses_and_releases_in_order(self):
        inputs = actions.key_combo_inputs(actions.KEY_ACTIONS["Previous Tab"])
        codes = [(item.ki.wVk, bool(item.ki.dwFlags & 2)) for item in inputs]
        self.assertEqual(codes, [
            (actions.VK_CONTROL, False), (actions.VK_SHIFT, False), (actions.VK_TAB, False),
            (actions.VK_TAB, True), (actions.VK_SHIFT, True), (actions.VK_CONTROL, True),
        ])

    def test_shortcut_rules(self):
        self.assertTrue(actions.valid_shortcut([17, 16, 84]))
        self.assertTrue(actions.valid_shortcut([116]))
        self.assertFalse(actions.valid_shortcut([17]))
        self.assertFalse(actions.valid_shortcut([84, 17]))
        self.assertFalse(actions.valid_shortcut([]))
        self.assertFalse(actions.valid_shortcut([17, 16, 18, 91, 17, 84]))
        self.assertFalse(actions.valid_shortcut(["17", 84]))

    def test_every_preset_action_exists(self):
        known = set(actions.KEY_ACTIONS) | set(actions.ZOOM_ACTIONS)
        for pair in actions.WHEEL_PRESETS.values():
            if pair:
                self.assertTrue(set(pair) <= known)
        for name in actions.BUTTON_ACTIONS:
            self.assertTrue(name in known or name in actions.LAUNCH_ACTIONS or name == actions.DO_NOTHING)


if __name__ == "__main__":
    unittest.main()
