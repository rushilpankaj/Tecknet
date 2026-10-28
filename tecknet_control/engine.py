"""Decides what happens to each side-wheel tilt and side-button click.

Pure logic with no Win32 calls, so it can be tested on its own. The input
thread (input_hook.py) feeds it events and gives it a host that runs timers
and actions.

Why the matching: a low-level mouse hook can block an event but cannot tell
which device sent it, while Raw Input tells the device but cannot block. A
horizontal scroll is therefore held back by the hook ("pending") until Raw
Input says where it came from: the TECKNET wheel runs the action, anything
else (a trackpad, another mouse) is sent on unchanged. If Raw Input arrives
first, it leaves a "credit" that the hook uses straight away. A scroll that
nobody claims within PENDING_TIMEOUT is sent on unchanged.

A notched wheel like the TECKNET's always moves in steps of 120. A smooth
scroll (trackpads, high-resolution wheels) sends other values; those pass
straight through with no delay, so trackpad scrolling stays fluid.
"""

from collections import deque
from dataclasses import dataclass, field

PASS = False
BLOCK = True

WHEEL_NOTCH = 120
PENDING_TIMEOUT = 0.03  # seconds
CREDIT_TIMEOUT = 0.03
FLUSH_TIMER = 3
FLUSH_INTERVAL_MS = 10
DOUBLE_TIMER = {1: 1, 2: 2}


@dataclass(frozen=True)
class EngineConfig:
    enabled: bool = False
    wheel: tuple | None = None  # (left action, right action); None = native scroll
    invert_wheel: bool = False
    only_target_devices: bool = True
    target_ids: frozenset = frozenset()
    # Per side button: the action to run (any object; run_action receives it),
    # or None for the normal Back / Forward click (single) or no double click.
    single_click: dict = field(default_factory=lambda: {1: None, 2: None})
    double_click: dict = field(default_factory=lambda: {1: None, 2: None})
    double_click_ms: int = 280


class _ButtonState:
    def __init__(self):
        self.waiting = False
        self.swallow_up = False


class InputEngine:
    def __init__(self, host, run_action, send_wheel, send_click):
        self.host = host
        self._run_action = run_action
        self._send_wheel = send_wheel
        self._send_click = send_click
        self.config = EngineConfig()
        self.pending = deque()  # (time, delta) waiting for Raw Input
        self.credits = deque()  # times of TECKNET wheel events seen first by Raw Input
        self.buttons = {1: _ButtonState(), 2: _ButtonState()}

    def configure(self, config):
        self.config = config
        self.flush_all()
        for button, state in self.buttons.items():
            if state.waiting:
                state.waiting = False
                self.host.kill_timer(DOUBLE_TIMER[button])
                self._single(button)

    # --- side wheel -------------------------------------------------------
    def wheel_active(self):
        return self.config.enabled and self.config.wheel is not None

    def _fire_wheel(self, delta):
        left, right = self.config.wheel
        tilt_right = delta > 0
        if self.config.invert_wheel:
            tilt_right = not tilt_right
        action = right if tilt_right else left
        self.host.post(lambda: self._run_action(action))

    def on_hook_wheel(self, delta, now):
        """A horizontal scroll seen by the hook. Returns BLOCK or PASS."""
        if not self.wheel_active():
            return PASS
        if not self.config.only_target_devices:
            self._fire_wheel(delta)
            return BLOCK
        if delta % WHEEL_NOTCH:
            return PASS  # smooth scroll: never the notched TECKNET wheel
        self._expire_credits(now)
        if self.credits:
            self.credits.popleft()
            self._fire_wheel(delta)
            return BLOCK
        self.pending.append((now, delta))
        if len(self.pending) == 1:
            self.host.set_timer(FLUSH_TIMER, FLUSH_INTERVAL_MS)
        return BLOCK

    def on_raw_wheel(self, from_target, now):
        """A horizontal scroll seen by Raw Input, with its device."""
        if not self.wheel_active() or not self.config.only_target_devices:
            return
        if self.pending:
            _, delta = self.pending.popleft()
            if from_target:
                self._fire_wheel(delta)
            else:
                self.host.post(lambda: self._send_wheel(delta))
            if not self.pending:
                self.host.kill_timer(FLUSH_TIMER)
        elif from_target:
            self.credits.append(now)

    def on_flush_timer(self, now):
        while self.pending and now - self.pending[0][0] >= PENDING_TIMEOUT:
            _, delta = self.pending.popleft()
            self.host.post(lambda d=delta: self._send_wheel(d))
        self._expire_credits(now)
        if not self.pending:
            self.host.kill_timer(FLUSH_TIMER)

    def flush_all(self):
        while self.pending:
            _, delta = self.pending.popleft()
            self.host.post(lambda d=delta: self._send_wheel(d))
        self.credits.clear()
        self.host.kill_timer(FLUSH_TIMER)

    def _expire_credits(self, now):
        while self.credits and now - self.credits[0] > CREDIT_TIMEOUT:
            self.credits.popleft()

    # --- side buttons -----------------------------------------------------
    def _single(self, button):
        single = self.config.single_click.get(button)
        if single is None:
            self.host.post(lambda: self._send_click(button))
        else:
            self.host.post(lambda: self._run_action(single))

    def on_button_down(self, button):
        if not self.config.enabled or button not in self.buttons:
            return PASS
        action = self.config.double_click.get(button)
        state = self.buttons[button]
        if action is None:
            # No double click to wait for: act at once.
            if self.config.single_click.get(button) is None:
                return PASS  # normal Back / Forward
            state.swallow_up = True
            self._single(button)
            return BLOCK
        state.swallow_up = True
        if state.waiting:
            state.waiting = False
            self.host.kill_timer(DOUBLE_TIMER[button])
            self.host.post(lambda: self._run_action(action))
            return BLOCK
        state.waiting = True
        self.host.set_timer(DOUBLE_TIMER[button], self.config.double_click_ms)
        return BLOCK

    def on_button_up(self, button):
        state = self.buttons.get(button)
        if state and state.swallow_up:
            state.swallow_up = False
            return BLOCK
        return PASS

    def on_double_timer(self, button):
        self.host.kill_timer(DOUBLE_TIMER[button])
        state = self.buttons[button]
        if state.waiting:
            state.waiting = False
            self._single(button)
