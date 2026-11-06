"""Precision mode: a slower pointer while a side button is held.

The change is never saved in Windows settings. The normal speed is also
written to RESTORE_FILE while it is slowed down, so that if the app dies at
that moment, the next start puts the speed back (restore_after_crash).
"""

import logging
import time

from . import winapi
from .config import APP_DIR

log = logging.getLogger(__name__)

RESTORE_FILE = APP_DIR / "pointer_speed.restore"
SLOWER = 3  # precision speed = normal speed / SLOWER


class PointerSpeed:
    def __init__(self):
        self.normal = None  # the speed to go back to, while slowed down
        self.slowed_at = 0.0

    @property
    def active(self):
        return self.normal is not None

    def slow_down(self):
        if self.active:
            return
        self.normal = winapi.pointer_speed()
        self.slowed_at = time.monotonic()
        try:
            RESTORE_FILE.parent.mkdir(parents=True, exist_ok=True)
            RESTORE_FILE.write_text(str(self.normal), encoding="utf-8")
        except OSError:
            log.warning("Could not save the pointer speed")
        winapi.set_pointer_speed(max(1, self.normal // SLOWER))

    def restore(self):
        if not self.active:
            return
        winapi.set_pointer_speed(self.normal)
        self.normal = None
        RESTORE_FILE.unlink(missing_ok=True)

    def restore_after_crash(self):
        """A previous run stopped while slowed down: undo it."""
        try:
            speed = int(RESTORE_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        if 1 <= speed <= 20:
            winapi.set_pointer_speed(speed)
            log.info("Pointer speed restored after an unexpected stop")
        RESTORE_FILE.unlink(missing_ok=True)
