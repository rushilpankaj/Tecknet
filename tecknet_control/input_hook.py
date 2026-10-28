"""The input thread: Raw Input, the low-level mouse hook and the engine's timers.

Everything runs on one thread with its own message loop, so hook calls,
Raw Input messages, timers and actions never run at the same time. The hook
is installed only while custom controls are on; Windows removes it by itself
if the app exits or crashes, so the mouse always returns to normal.
"""

import ctypes
import logging
import threading
import time
from collections import deque
from ctypes import wintypes

from . import actions, winapi
from .device_ids import device_id, transport
from .engine import DOUBLE_TIMER, FLUSH_TIMER, EngineConfig, InputEngine

log = logging.getLogger(__name__)

WM_APP_EFFECTS = winapi.WM_APP + 1
WM_APP_CONFIG = winapi.WM_APP + 2
WATCHDOG_TIMER = 10
WATCHDOG_INTERVAL_MS = 5000
CLASS_NAME = "TecknetControlInput"


class InputThread:
    def __init__(self):
        self.engine = InputEngine(
            self, actions.run_action, actions.send_horizontal_wheel, actions.send_side_click
        )
        self.last_activity = {}  # transport -> time of the last TECKNET input
        self.identify_callback = None  # called once with (device id, transport)
        self.side_button_callback = None  # called with 1 or 2 when a TECKNET side button is pressed
        self._config = EngineConfig()
        self._effects = deque()
        self._effects_posted = False
        self._devices = {}
        self._hwnd = None
        self._hook = None
        self._hook_calls = 0
        self._watchdog_calls = 0
        self._watchdog_cursor = (0, 0)
        self._raw_buffer = ctypes.create_string_buffer(ctypes.sizeof(winapi.RAWINPUT) + 16)
        self._ready = threading.Event()
        self._thread = None
        # Keep references to the callbacks for as long as Windows can call them.
        self._hook_proc = winapi.HOOKPROC(self._on_hook)
        self._wnd_proc = winapi.WNDPROC(self._on_message)

    # --- called from the UI thread ----------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, name="input", daemon=True)
        self._thread.start()
        self._ready.wait(3)

    def apply(self, config):
        self._config = config
        if self._hwnd:
            winapi.user32.PostMessageW(self._hwnd, WM_APP_CONFIG, 0, 0)

    def stop(self):
        if self._hwnd:
            winapi.user32.PostMessageW(self._hwnd, winapi.WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(2)

    def hook_installed(self):
        return bool(self._hook)

    def seconds_since_activity(self, kind):
        last = self.last_activity.get(kind)
        return None if last is None else time.monotonic() - last

    # --- host interface used by the engine (input thread only) -------------
    def set_timer(self, timer_id, milliseconds):
        winapi.user32.SetTimer(self._hwnd, timer_id, milliseconds, None)

    def kill_timer(self, timer_id):
        winapi.user32.KillTimer(self._hwnd, timer_id)

    def post(self, effect):
        self._effects.append(effect)
        if not self._effects_posted:
            self._effects_posted = True
            winapi.user32.PostMessageW(self._hwnd, WM_APP_EFFECTS, 0, 0)

    # --- input thread -------------------------------------------------------
    def _run(self):
        instance = winapi.kernel32.GetModuleHandleW(None)
        window_class = winapi.WNDCLASSW(lpfnWndProc=self._wnd_proc, hInstance=instance, lpszClassName=CLASS_NAME)
        winapi.user32.RegisterClassW(ctypes.byref(window_class))
        self._hwnd = winapi.user32.CreateWindowExW(
            0, CLASS_NAME, CLASS_NAME, 0, 0, 0, 0, 0,
            wintypes.HWND(winapi.HWND_MESSAGE), None, instance, None,
        )
        if not self._hwnd:
            log.error("Could not create the input window (error %s)", ctypes.get_last_error())
            self._ready.set()
            return
        device = winapi.RAWINPUTDEVICE(1, 2, winapi.RIDEV_INPUTSINK, self._hwnd)  # generic desktop / mouse
        if not winapi.user32.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(device)):
            log.error("Raw Input registration failed (error %s)", ctypes.get_last_error())
        self._apply_config()
        self._ready.set()
        message = wintypes.MSG()
        while winapi.user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            winapi.user32.TranslateMessage(ctypes.byref(message))
            winapi.user32.DispatchMessageW(ctypes.byref(message))
        self._hwnd = None

    def _apply_config(self):
        config = self._config
        self.engine.configure(config)
        wanted = config.enabled and (
            config.wheel is not None
            or any(config.double_click.values())
            or any(config.single_click.values())
        )
        if wanted and not self._hook:
            self._install_hook()
        elif not wanted and self._hook:
            self._remove_hook()

    def _install_hook(self):
        instance = winapi.kernel32.GetModuleHandleW(None)
        self._hook = winapi.user32.SetWindowsHookExW(winapi.WH_MOUSE_LL, self._hook_proc, instance, 0)
        if self._hook:
            self.set_timer(WATCHDOG_TIMER, WATCHDOG_INTERVAL_MS)
            log.info("Mouse hook installed")
        else:
            log.error("Mouse hook failed (error %s)", ctypes.get_last_error())

    def _remove_hook(self):
        self.kill_timer(WATCHDOG_TIMER)
        if self._hook:
            winapi.user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            log.info("Mouse hook removed")

    def _check_hook(self):
        """Windows silently drops a hook that answers too slowly; put it back."""
        point = winapi.POINT()
        winapi.user32.GetCursorPos(ctypes.byref(point))
        cursor = (point.x, point.y)
        moved = cursor != self._watchdog_cursor
        silent = self._hook_calls == self._watchdog_calls
        self._watchdog_cursor = cursor
        self._watchdog_calls = self._hook_calls
        if self._hook and moved and silent:
            log.warning("Mouse hook stopped responding; reinstalling")
            winapi.user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            self._install_hook()

    def _on_hook(self, code, message, data):
        if code >= 0:
            self._hook_calls += 1
            if message != winapi.WM_MOUSEMOVE:
                try:
                    if self._handle_hook_event(message, data):
                        return 1
                except Exception:
                    log.exception("Hook error")
        return winapi.user32.CallNextHookEx(None, code, message, data)

    def _handle_hook_event(self, message, data):
        info = winapi.MSLLHOOKSTRUCT.from_address(data)
        high_word = (info.mouseData >> 16) & 0xFFFF
        injected = bool(info.flags & winapi.LLMHF_INJECTED)
        if message == winapi.WM_MOUSEHWHEEL:
            delta = ctypes.c_short(high_word).value
            if injected:
                log.debug("hook wheel %+d injected: pass", delta)
                return False
            blocked = self.engine.on_hook_wheel(delta, time.monotonic())
            log.debug("hook wheel %+d: %s", delta, "hold/act" if blocked else "pass")
            return blocked
        if injected:
            return False  # sent by a program (including this one): leave it alone
        if message == winapi.WM_XBUTTONDOWN:
            return self.engine.on_button_down(high_word)
        if message == winapi.WM_XBUTTONUP:
            return self.engine.on_button_up(high_word)
        return False

    def _on_message(self, hwnd, message, wparam, lparam):
        try:
            if message == winapi.WM_INPUT:
                self._handle_raw_input(lparam)
            elif message == WM_APP_EFFECTS:
                self._run_effects()
                return 0
            elif message == WM_APP_CONFIG:
                self._apply_config()
                self._run_effects()
                return 0
            elif message == winapi.WM_TIMER:
                self._handle_timer(wparam)
                self._run_effects()
                return 0
            elif message == winapi.WM_CLOSE:
                self.engine.flush_all()
                self._run_effects()
                self._remove_hook()
                winapi.user32.DestroyWindow(hwnd)
                return 0
            elif message == winapi.WM_DESTROY:
                winapi.user32.PostQuitMessage(0)
                return 0
        except Exception:
            log.exception("Input thread error")
        return winapi.user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _handle_timer(self, timer_id):
        if timer_id == FLUSH_TIMER:
            self.engine.on_flush_timer(time.monotonic())
        elif timer_id == WATCHDOG_TIMER:
            self._check_hook()
        else:
            for button, button_timer in DOUBLE_TIMER.items():
                if timer_id == button_timer:
                    self.engine.on_double_timer(button)

    def _device(self, handle):
        known = self._devices.get(handle)
        if known is None:
            name = winapi.raw_device_name(handle)
            known = (device_id(name), transport(name))
            self._devices[handle] = known
        return known

    def _handle_raw_input(self, lparam):
        size = wintypes.UINT(ctypes.sizeof(self._raw_buffer))
        header_size = ctypes.sizeof(winapi.RAWINPUTHEADER)
        result = winapi.user32.GetRawInputData(lparam, winapi.RID_INPUT, self._raw_buffer, ctypes.byref(size), header_size)
        if result in (0, 0xFFFFFFFF):
            return
        raw = winapi.RAWINPUT.from_buffer(self._raw_buffer)
        if raw.header.dwType != winapi.RIM_TYPEMOUSE:
            return
        identifier, kind = self._device(raw.header.hDevice)
        now = time.monotonic()
        from_target = identifier in self._config.target_ids
        if from_target:
            self.last_activity[kind] = now
        flags = raw.mouse.usButtonFlags
        if flags & winapi.RI_MOUSE_HWHEEL:
            log.debug("raw wheel %+d from %s (%s)", ctypes.c_short(raw.mouse.usButtonData).value, identifier or "?", "TECKNET" if from_target else "other")
            self.engine.on_raw_wheel(from_target, now)
        side_button = self.side_button_callback
        if side_button and from_target:
            if flags & winapi.RI_MOUSE_BUTTON_4_DOWN:
                side_button(1)
            elif flags & winapi.RI_MOUSE_BUTTON_5_DOWN:
                side_button(2)
        identify_flags = winapi.RI_MOUSE_HWHEEL | winapi.RI_MOUSE_BUTTON_4_DOWN | winapi.RI_MOUSE_BUTTON_5_DOWN
        callback = self.identify_callback
        if callback and identifier and flags & identify_flags:
            self.identify_callback = None
            callback(identifier, kind)

    def _run_effects(self):
        self._effects_posted = False
        while self._effects:
            effect = self._effects.popleft()
            try:
                effect()
            except Exception:
                log.exception("Action failed")
