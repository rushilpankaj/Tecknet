"""Decides what happens to each side-wheel tilt and side-button press.

Pure logic with no Win32 calls, so it can be tested on its own. The input
thread (input_hook.py) feeds it events and gives it a host that runs timers,
actions, reads the app in front and changes the pointer speed.

Side wheel. A low-level mouse hook can block an event but cannot tell which
device sent it, while Raw Input tells the device but cannot block. A
horizontal scroll is therefore held back by the hook ("pending") until Raw
Input says where it came from: the TECKNET wheel runs the action, anything
else (a trackpad, another mouse) is sent on unchanged. If Raw Input arrives
first, it leaves a "credit" that the hook uses straight away. A scroll that
nobody claims within PENDING_TIMEOUT is sent on unchanged. A notched wheel
like the TECKNET's always moves in steps of 120; smooth scrolls (trackpads)
send other values and pass straight through with no delay.

Side buttons, per button:
- click: a short press. With a double-click action it waits for a second
  press first; with none it acts at once (or is left to Windows).
- hold: pressed for HOLD_MS runs the hold action; "precision" slows the
  pointer while held; "gestures" looks at where the mouse moved between
  press and release and runs the action for that direction.
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
HOLD_TIMER = {1: 5, 2: 6}
HOLD_MS = 450
GESTURE_DISTANCE = 50  # pixels the mouse must move to count as a gesture
# Turning the wheel quickly repeats accelerated actions: (seconds since last, times).
ACCELERATION = ((0.06, 3), (0.12, 2))

GESTURES = "gestures"
PRECISION = "precision"


@dataclass(frozen=True)
class EngineConfig:
    enabled: bool = False
    wheel: tuple | None = None  # (left action, right action); None = native scroll
    wheel_by_app: dict = field(default_factory=dict)  # "chrome.exe" -> pair or None
    invert_wheel: bool = False
    accelerated: frozenset = frozenset()  # actions repeated when the wheel turns fast
    target_ids: frozenset = frozenset()
    # Per side button: the action to run (any object; run_action receives it),
    # or None for the normal Back / Forward click (single), no double click,
    # or no hold. hold may also be GESTURES or PRECISION.
    single_click: dict = field(default_factory=lambda: {1: None, 2: None})
    double_click: dict = field(default_factory=lambda: {1: None, 2: None})
    hold: dict = field(default_factory=lambda: {1: None, 2: None})
    gestures: dict = field(default_factory=dict)  # "left"/"right"/"up"/"down" -> action
    double_click_ms: int = 280


class _ButtonState:
    def __init__(self):
        self.waiting = False  # first click seen, waiting for a second one
        self.swallow_up = False
        self.down = False  # pressed, in hold mode
        self.down_at = (0, 0)
        self.hold_fired = False


def gesture_direction(start, end, distance=GESTURE_DISTANCE):
    dx, dy = end[0] - start[0], end[1] - start[1]
    if max(abs(dx), abs(dy)) < distance:
        return None
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


class InputEngine:
    def __init__(self, host, run_action, send_wheel, send_click):
        self.host = host
        self._run_action = run_action
        self._send_wheel = send_wheel
        self._send_click = send_click
        self.config = EngineConfig()
        self.pending = deque()  # (time, delta, pair) waiting for Raw Input
        self.credits = deque()  # times of TECKNET wheel events seen first by Raw Input
        self.buttons = {1: _ButtonState(), 2: _ButtonState()}
        self.last_wheel_action = -1.0
        self.precision_on = False

    def configure(self, config):
        self.config = config
        self.flush_all()
        self._set_precision(False)
        for button, state in self.buttons.items():
            self.host.kill_timer(HOLD_TIMER[button])
            state.down = False
            if state.waiting:
                state.waiting = False
                self.host.kill_timer(DOUBLE_TIMER[button])
                self._single(button)

    def _run(self, action, times=1):
        for _ in range(times):
            self.host.post(lambda: self._run_action(action))

    # --- side wheel -------------------------------------------------------
    def wheel_active(self):
        config = self.config
        if not config.enabled:
            return False
        return config.wheel is not None or any(pair is not None for pair in config.wheel_by_app.values())

    def wheel_pair(self):
        """The pair for the app in front (its profile), else the default."""
        if self.config.wheel_by_app:
            app = self.host.foreground_app()
            if app in self.config.wheel_by_app:
                return self.config.wheel_by_app[app]
        return self.config.wheel

    def _fire_wheel(self, delta, pair, now):
        left, right = pair
        tilt_right = delta > 0
        if self.config.invert_wheel:
            tilt_right = not tilt_right
        action = right if tilt_right else left
        times = 1
        if action in self.config.accelerated:
            elapsed = now - self.last_wheel_action
            times = next((n for limit, n in ACCELERATION if elapsed < limit), 1)
        self.last_wheel_action = now
        self._run(action, times)

    def on_hook_wheel(self, delta, now):
        """A horizontal scroll seen by the hook. Returns BLOCK or PASS."""
        if not self.wheel_active():
            return PASS
        pair = self.wheel_pair()
        if pair is None:
            return PASS  # normal horizontal scroll in this app
        if delta % WHEEL_NOTCH:
            return PASS  # smooth scroll: never the notched TECKNET wheel
        self._expire_credits(now)
        if self.credits:
            self.credits.popleft()
            self._fire_wheel(delta, pair, now)
            return BLOCK
        self.pending.append((now, delta, pair))
        if len(self.pending) == 1:
            self.host.set_timer(FLUSH_TIMER, FLUSH_INTERVAL_MS)
        return BLOCK

    def on_raw_wheel(self, from_target, now):
        """A horizontal scroll seen by Raw Input, with its device."""
        if not self.wheel_active():
            return
        if self.pending:
            _, delta, pair = self.pending.popleft()
            if from_target:
                self._fire_wheel(delta, pair, now)
            else:
                self.host.post(lambda: self._send_wheel(delta))
            if not self.pending:
                self.host.kill_timer(FLUSH_TIMER)
        elif from_target:
            self.credits.append(now)

    def on_flush_timer(self, now):
        while self.pending and now - self.pending[0][0] >= PENDING_TIMEOUT:
            _, delta, _ = self.pending.popleft()
            self.host.post(lambda d=delta: self._send_wheel(d))
        self._expire_credits(now)
        if not self.pending:
            self.host.kill_timer(FLUSH_TIMER)

    def flush_all(self):
        while self.pending:
            _, delta, _ = self.pending.popleft()
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
            self._run(single)

    def _set_precision(self, on):
        if on != self.precision_on:
            self.precision_on = on
            self.host.post(lambda: self.host.precision(on))

    def _click(self, button):
        """A complete short click on a button that has a hold action."""
        double = self.config.double_click.get(button)
        state = self.buttons[button]
        if double is None:
            self._single(button)
        elif state.waiting:
            state.waiting = False
            self.host.kill_timer(DOUBLE_TIMER[button])
            self._run(double)
        else:
            state.waiting = True
            self.host.set_timer(DOUBLE_TIMER[button], self.config.double_click_ms)

    def on_button_down(self, button, position=(0, 0)):
        if not self.config.enabled or button not in self.buttons:
            return PASS
        state = self.buttons[button]
        hold = self.config.hold.get(button)
        if hold is not None:
            state.down = True
            state.down_at = position
            state.hold_fired = False
            state.swallow_up = True
            if hold != GESTURES:
                self.host.set_timer(HOLD_TIMER[button], HOLD_MS)
            return BLOCK
        action = self.config.double_click.get(button)
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
            self._run(action)
            return BLOCK
        state.waiting = True
        self.host.set_timer(DOUBLE_TIMER[button], self.config.double_click_ms)
        return BLOCK

    def cancel_holds(self):
        """Forget pressed buttons (their release was lost) and leave precision mode."""
        for button, state in self.buttons.items():
            if state.down:
                state.down = False
                state.swallow_up = False
                self.host.kill_timer(HOLD_TIMER[button])
        self._set_precision(False)

    def on_hold_timer(self, button):
        self.host.kill_timer(HOLD_TIMER[button])
        state = self.buttons[button]
        hold = self.config.hold.get(button)
        if not state.down or hold is None or hold == GESTURES:
            return
        state.hold_fired = True
        if hold == PRECISION:
            self._set_precision(True)
        else:
            self._run(hold)

    def on_button_up(self, button, position=(0, 0)):
        state = self.buttons.get(button)
        if state is None:
            return PASS
        if state.down:
            state.down = False
            state.swallow_up = False
            self.host.kill_timer(HOLD_TIMER[button])
            hold = self.config.hold.get(button)
            if state.hold_fired:
                if hold == PRECISION:
                    self._set_precision(False)
                return BLOCK
            if hold == GESTURES:
                direction = gesture_direction(state.down_at, position)
                if direction:
                    action = self.config.gestures.get(direction)
                    if action is not None:
                        self._run(action)
                    return BLOCK
            self._click(button)
            return BLOCK
        if state.swallow_up:
            state.swallow_up = False
            return BLOCK
        return PASS

    def on_double_timer(self, button):
        self.host.kill_timer(DOUBLE_TIMER[button])
        state = self.buttons[button]
        if state.waiting:
            state.waiting = False
            self._single(button)
