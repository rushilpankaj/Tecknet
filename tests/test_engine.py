import unittest

from tecknet_control.engine import (
    BLOCK, DOUBLE_TIMER, FLUSH_TIMER, GESTURES, HOLD_TIMER, PASS, PENDING_TIMEOUT, PRECISION,
    EngineConfig, InputEngine, gesture_direction,
)

VOLUME = ("Volume Down", "Volume Up")


class FakeHost:
    def __init__(self):
        self.timers = {}
        self.effects = []
        self.app = "explorer.exe"
        self.precision_calls = []

    def foreground_app(self):
        return self.app

    def precision(self, on):
        self.precision_calls.append(on)

    def set_timer(self, timer_id, ms):
        self.timers[timer_id] = ms

    def kill_timer(self, timer_id):
        self.timers.pop(timer_id, None)

    def post(self, effect):
        self.effects.append(effect)

    def run(self):
        effects, self.effects = self.effects, []
        for effect in effects:
            effect()


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.done = []
        self.engine = InputEngine(
            self.host,
            run_action=lambda action: self.done.append(("action", action)),
            send_wheel=lambda delta: self.done.append(("wheel", delta)),
            send_click=lambda button: self.done.append(("click", button)),
        )

    def tilt(self, delta, now):
        """The TECKNET side wheel: Raw Input names the device, then the hook sees it."""
        self.engine.on_raw_wheel(from_target=True, now=now)
        return self.engine.on_hook_wheel(delta, now)

    def configure(self, **changes):
        values = dict(enabled=True, wheel=VOLUME, target_ids=frozenset({"25A7:FA61"}))
        values.update(changes)
        self.engine.configure(EngineConfig(**values))
        self.host.run()

    # --- side wheel --------------------------------------------------------
    def test_disabled_passes_everything(self):
        self.configure(enabled=False)
        self.assertEqual(self.engine.on_hook_wheel(120, 0.0), PASS)
        self.assertEqual(self.engine.on_button_down(1), PASS)

    def test_horizontal_scroll_preset_is_native(self):
        self.configure(wheel=None)
        self.assertEqual(self.engine.on_hook_wheel(120, 0.0), PASS)

    def test_tecknet_wheel_after_hook_runs_action(self):
        self.configure()
        self.assertEqual(self.engine.on_hook_wheel(120, 0.0), BLOCK)
        self.engine.on_raw_wheel(from_target=True, now=0.001)
        self.host.run()
        self.assertEqual(self.done, [("action", "Volume Up")])
        self.assertNotIn(FLUSH_TIMER, self.host.timers)

    def test_tecknet_wheel_before_hook_uses_credit(self):
        self.configure()
        self.engine.on_raw_wheel(from_target=True, now=0.0)
        self.assertEqual(self.engine.on_hook_wheel(-120, 0.002), BLOCK)
        self.host.run()
        self.assertEqual(self.done, [("action", "Volume Down")])

    def test_smooth_trackpad_scroll_passes_with_no_delay(self):
        self.configure()
        for delta in (17, -3, 45, 119, -121):
            self.assertEqual(self.engine.on_hook_wheel(delta, 0.0), PASS)
        self.assertEqual(len(self.engine.pending), 0)
        self.assertNotIn(FLUSH_TIMER, self.host.timers)

    def test_notched_scroll_from_other_device_is_sent_on_unchanged(self):
        self.configure()
        self.engine.on_hook_wheel(-120, 0.0)
        self.engine.on_raw_wheel(from_target=False, now=0.001)
        self.host.run()
        self.assertEqual(self.done, [("wheel", -120)])

    def test_unclaimed_scroll_is_released_after_timeout(self):
        self.configure()
        deltas = (120, 120, -120, 240, 120)
        for index, delta in enumerate(deltas):
            self.engine.on_hook_wheel(delta, index * 0.001)
        self.assertIn(FLUSH_TIMER, self.host.timers)
        self.engine.on_flush_timer(0.001)
        self.host.run()
        self.assertEqual(self.done, [])
        self.engine.on_flush_timer(PENDING_TIMEOUT + 0.01)
        self.host.run()
        self.assertEqual(self.done, [("wheel", d) for d in deltas])
        self.assertNotIn(FLUSH_TIMER, self.host.timers)

    def test_old_credit_is_not_used(self):
        self.configure()
        self.engine.on_raw_wheel(from_target=True, now=0.0)
        self.engine.on_hook_wheel(120, 1.0)
        self.engine.on_flush_timer(1.0 + PENDING_TIMEOUT)
        self.host.run()
        self.assertEqual(self.done, [("wheel", 120)])

    def test_invert_wheel(self):
        self.configure(invert_wheel=True)
        self.tilt(120, 0.0)
        self.host.run()
        self.assertEqual(self.done, [("action", "Volume Down")])

    def test_turning_off_releases_pending_scroll(self):
        self.configure()
        self.engine.on_hook_wheel(120, 0.0)
        self.configure(enabled=False)
        self.assertEqual(self.done, [("wheel", 120)])

    # --- side buttons --------------------------------------------------------
    def test_single_click_is_sent_after_delay(self):
        self.configure(double_click={1: ("Calculator", ""), 2: None}, double_click_ms=300)
        self.assertEqual(self.engine.on_button_down(1), BLOCK)
        self.assertEqual(self.engine.on_button_up(1), BLOCK)
        self.assertEqual(self.host.timers[DOUBLE_TIMER[1]], 300)
        self.engine.on_double_timer(1)
        self.host.run()
        self.assertEqual(self.done, [("click", 1)])

    def test_double_click_runs_action(self):
        self.configure(double_click={1: None, 2: ("Open Program...", r"C:\app.exe")})
        self.engine.on_button_down(2)
        self.engine.on_button_up(2)
        self.engine.on_button_down(2)
        self.engine.on_button_up(2)
        self.host.run()
        self.assertEqual(self.done, [("action", ("Open Program...", r"C:\app.exe"))])
        self.assertNotIn(DOUBLE_TIMER[2], self.host.timers)

    def test_button_without_double_action_has_no_delay(self):
        self.configure(double_click={1: None, 2: None})
        self.assertEqual(self.engine.on_button_down(1), PASS)
        self.assertEqual(self.engine.on_button_up(1), PASS)

    def test_custom_single_click_without_double_acts_at_once(self):
        self.configure(single_click={1: ("Play / Pause", ""), 2: None}, double_click={1: None, 2: None})
        self.assertEqual(self.engine.on_button_down(1), BLOCK)
        self.assertEqual(self.engine.on_button_up(1), BLOCK)
        self.host.run()
        self.assertEqual(self.done, [("action", ("Play / Pause", ""))])
        self.assertEqual(self.host.timers, {})
        self.assertEqual(self.engine.on_button_down(2), PASS)  # button 2 stays Forward

    def test_custom_single_click_with_double_waits(self):
        self.configure(single_click={1: ("Mute", ""), 2: None}, double_click={1: ("Calculator", ""), 2: None})
        self.engine.on_button_down(1)
        self.engine.on_button_up(1)
        self.engine.on_double_timer(1)
        self.host.run()
        self.assertEqual(self.done, [("action", ("Mute", ""))])

    # --- app profiles and acceleration --------------------------------------
    def test_app_profile_changes_the_wheel(self):
        self.configure(wheel_by_app={"chrome.exe": ("Previous Tab", "Next Tab"), "game.exe": None})
        self.host.app = "chrome.exe"
        self.tilt(120, 0.0)
        self.host.app = "game.exe"
        self.assertEqual(self.engine.on_hook_wheel(120, 1.0), PASS)  # normal scroll there
        self.host.app = "notepad.exe"
        self.tilt(120, 2.0)
        self.host.run()
        self.assertEqual(self.done, [("action", "Next Tab"), ("action", "Volume Up")])

    def test_profile_alone_turns_the_wheel_on(self):
        self.configure(wheel=None, wheel_by_app={"chrome.exe": ("Previous Tab", "Next Tab")})
        self.assertTrue(self.engine.wheel_active())
        self.assertEqual(self.engine.on_hook_wheel(120, 0.0), PASS)  # not in Chrome

    def test_fast_turns_repeat_accelerated_actions(self):
        self.configure(accelerated=frozenset({"Volume Up"}))
        for now in (0.0, 0.03, 0.10, 1.0):
            self.tilt(120, now)
        self.host.run()
        self.assertEqual([a for _, a in self.done], ["Volume Up"] * (1 + 3 + 2 + 1))

    # --- hold, gestures, precision -----------------------------------------
    def test_short_press_with_hold_action_is_a_click(self):
        self.configure(hold={1: "Task Manager", 2: None}, double_click={1: None, 2: None})
        self.assertEqual(self.engine.on_button_down(1, (0, 0)), BLOCK)
        self.assertEqual(self.engine.on_button_up(1, (0, 0)), BLOCK)
        self.host.run()
        self.assertEqual(self.done, [("click", 1)])

    def test_long_press_runs_hold_action_once(self):
        self.configure(hold={1: "Task Manager", 2: None})
        self.engine.on_button_down(1, (0, 0))
        self.assertIn(HOLD_TIMER[1], self.host.timers)
        self.engine.on_hold_timer(1)
        self.engine.on_button_up(1, (0, 0))
        self.host.run()
        self.assertEqual(self.done, [("action", "Task Manager")])

    def test_hold_then_double_click_still_works(self):
        self.configure(hold={1: "Task Manager", 2: None}, double_click={1: "Calculator", 2: None})
        for _ in range(2):
            self.engine.on_button_down(1, (0, 0))
            self.engine.on_button_up(1, (0, 0))
        self.host.run()
        self.assertEqual(self.done, [("action", "Calculator")])

    def test_gestures(self):
        gestures = {"left": "Prev", "right": "Next", "up": "Max", "down": None}
        self.configure(hold={1: GESTURES, 2: None}, gestures=gestures)
        for end in ((120, 10), (-80, 0), (5, -90), (0, 90)):
            self.engine.on_button_down(1, (0, 0))
            self.assertEqual(self.engine.on_button_up(1, end), BLOCK)
        self.engine.on_button_down(1, (0, 0))
        self.engine.on_button_up(1, (10, 5))  # barely moved: a normal click
        self.host.run()
        self.assertEqual(self.done, [("action", "Next"), ("action", "Prev"), ("action", "Max"), ("click", 1)])

    def test_precision_while_held(self):
        self.configure(hold={1: None, 2: PRECISION})
        self.engine.on_button_down(2, (0, 0))
        self.engine.on_hold_timer(2)
        self.host.run()
        self.assertEqual(self.host.precision_calls, [True])
        self.engine.on_button_up(2, (0, 0))
        self.host.run()
        self.assertEqual(self.host.precision_calls, [True, False])
        self.assertEqual(self.done, [])

    def test_turning_off_restores_precision(self):
        self.configure(hold={1: PRECISION, 2: None})
        self.engine.on_button_down(1, (0, 0))
        self.engine.on_hold_timer(1)
        self.configure(enabled=False)
        self.assertEqual(self.host.precision_calls, [True, False])

    def test_lost_release_turns_precision_off(self):
        self.configure(hold={1: PRECISION, 2: None})
        self.engine.on_button_down(1, (0, 0))
        self.engine.on_hold_timer(1)
        self.engine.cancel_holds()
        self.host.run()
        self.assertEqual(self.host.precision_calls, [True, False])
        self.assertEqual(self.engine.on_button_up(1, (0, 0)), PASS)  # late release is harmless

    def test_gesture_direction(self):
        self.assertIsNone(gesture_direction((0, 0), (30, -30)))
        self.assertEqual(gesture_direction((100, 100), (100, 300)), "down")

    def test_turning_off_while_waiting_sends_the_click(self):
        self.configure(double_click={1: ("Calculator", ""), 2: None})
        self.engine.on_button_down(1)
        self.configure(enabled=False)
        self.assertEqual(self.done, [("click", 1)])


if __name__ == "__main__":
    unittest.main()
