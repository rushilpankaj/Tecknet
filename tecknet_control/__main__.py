"""Start the app.

Options:
  --minimized  start in the system tray (used by Start with Windows)
  --exit       close the running copy (used by the installer)
  --debug      write every side-wheel event to the log (for bug reports)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import __version__, config, system


def setup_logging(debug=False):
    config.APP_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(config.LOG_FILE, maxBytes=256_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, handlers=[handler])
    # Pillow writes its own debug lines; keep the log about the mouse.
    logging.getLogger("PIL").setLevel(logging.INFO)


def main(args=None):
    args = sys.argv[1:] if args is None else args
    instance = system.SingleInstance()
    if "--exit" in args:
        system.signal_running_instance(system.EXIT_EVENT)
        return 0
    if instance.already_running:
        system.signal_running_instance(system.SHOW_EVENT)
        return 0

    setup_logging(debug="--debug" in args)
    logging.getLogger(__name__).info("Tecknet Control %s starting", __version__)
    system.clean_up_v16()

    from .app import App
    from .input_hook import InputThread

    input_thread = InputThread()
    input_thread.start()
    app = App(instance, input_thread, start_minimized="--minimized" in args)
    app.mainloop()
    input_thread.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
