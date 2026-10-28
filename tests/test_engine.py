import unittest

from tecknet_control.engine import (
    BLOCK, DOUBLE_TIMER, FLUSH_TIMER, PASS, PENDING_TIMEOUT, EngineConfig, InputEngine,
)

VOLUME = ("Volume Down", "Volume Up")


class FakeHost:
    def __init__(self):
        self.timers = {}
        self.effects = []

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

    def test_all_devices_mode_acts_immediately(self):
        self.configure(only_target_devices=False)
        self.assertEqual(self.engine.on_hook_wheel(120, 0.0), BLOCK)
        self.host.run()
        self.assertEqual(self.done, [("action", "Volume Up")])

    def test_invert_wheel(self):
        self.configure(only_target_devices=False, invert_wheel=True)
        self.engine.on_hook_wheel(120, 0.0)
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

    def test_turning_off_while_waiting_sends_the_click(self):
        self.configure(double_click={1: ("Calculator", ""), 2: None})
        self.engine.on_button_down(1)
        self.configure(enabled=False)
        self.assertEqual(self.done, [("click", 1)])


if __name__ == "__main__":
    unittest.main()
