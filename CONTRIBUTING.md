# Contributing

Thanks for helping. Tecknet Control is meant to stay **small, simple and safe**:
anyone who knows basic Python should be able to change one part without
understanding the rest.

## Get started

```bat
install.bat                         rem Python packages (once)
run.bat                             rem start from source, no console
py TecknetControl.pyw --debug       rem every side-wheel event goes to the log
py -m unittest discover -s tests -t .
build.bat                           rem tests, app folder and installer
```

The log and settings live in `%APPDATA%\TecknetControl\`.

## How it works, in one picture

```
 mouse ──► Windows ──► input_hook.py ──► engine.py ──► actions.py ──► Windows
             │          (hook + Raw Input)  (decides)   (keys, apps)
             │
             └──► devices.py ──► app.py / ui/  (status, battery, settings)
                                    │
                                    └──► config.py ──► settings.json
```

1. `input_hook.py` sees every side-wheel tilt and side-button press (a
   low-level mouse hook) and which device sent it (Raw Input).
2. `engine.py` decides: block it and run an action, or let it through.
   It has no Windows calls, so it is fully tested.
3. `actions.py` sends the result: key presses, Ctrl + wheel, opening apps.

## Where to change things

| I want to… | Change |
|---|---|
| add an action to the menus (e.g. "Lock screen") | `actions.py`: one line in `KEY_ACTIONS` or `LAUNCH_ACTIONS`, then its name in `BUTTON_ACTIONS` |
| add a side-wheel mode (e.g. "Brightness") | `actions.py`: one line in `WHEEL_PRESETS` with its (left, right) actions |
| change colours, fonts, spacing | `ui/theme.py` only |
| change a card in the window | `ui/mouse_card.py`, `ui/controls_panel.py` (wheel, buttons), `ui/profiles_panel.py` (app profiles), `ui/app_card.py` (app settings) |
| change precision mode | `pointer_speed.py` |
| add a setting | `config.py`: default in `DEFAULTS` (checked automatically), then pass it to the engine in `engine_config()` |
| change click, double-click, hold or gesture timing | `engine.py`: the constants at the top |
| support another mouse model | `device_ids.py` (`TECKNET_IDS`) and `devices.py` (`MOUSE_NAME_PREFIX`) |
| change the installer | `installer/TecknetControl.iss` |

Every file starts with a short comment saying what it does.

## Rules that keep it simple and safe

- **No network access, no telemetry, no administrator rights.**
- **No shell commands**: no `shell=True`, no PowerShell. Use the Windows API
  (`winapi.py`) or `os.startfile`.
- **Settings are checked on load** (`config.py`): a damaged file must never
  stop the app, and programs to open must be existing local `.exe` / `.lnk`.
- **The hook must answer fast**: decide in `engine.py`, then do the work after
  (`host.post`). Never wait, read files or start programs inside the hook.
- **The mouse must always come back to normal**: switching controls off,
  exiting or crashing must leave Back, Forward, horizontal scroll and the
  pointer speed as Windows had them.
- **One clear way per thing**: no new libraries unless there is no simple
  alternative; prefer a short, plain function to a clever one.
- Keep files small (about 300 lines); split a file that grows past it.

## Before a pull request

1. Add or update a test in `tests/` for any change to `engine.py` or `config.py`.
2. Run the tests: `py -m unittest discover -s tests -t .`
3. Try it with the mouse: `run.bat`, then use the feature.
4. Add a line to `CHANGELOG.md`.
