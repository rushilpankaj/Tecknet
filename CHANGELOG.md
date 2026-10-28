# Changelog

## 1.7.0

- AutoHotkey is no longer needed: the app handles the mouse itself.
- The side-wheel action applies to the TECKNET mouse only. Trackpad
  scrolling is no longer turned into volume changes, and the AutoHotkey
  "71 hotkeys have been received" warning is gone.
- Smooth scrolling (trackpads) passes through with no delay.
- The mouse returns to normal even if the app is closed from Task Manager
  or crashes.
- New window design: clearer cards, notes under each setting, neutral menus,
  faster scrolling, sharp icons.
- Side buttons: a choice for the click as well as the double click; any app
  or any keyboard shortcut on each; pressing a side button highlights it in
  the window.
- New: Virtual Desktops wheel preset; Task View, Show Desktop and Screenshot
  for the side buttons; reverse wheel direction; double-click wait;
  *Add mouse* for other mice; low battery notification; custom controls
  switch in the tray menu.
- Changes apply immediately (no Apply button).
- A side button set to *Do Nothing* gives Back / Forward with no delay.
- Only one copy of the app runs; opening it again shows the window.
- Bluetooth mice named TK-MS029 are found automatically (no fixed address).
- Battery, USB and start-up checks no longer start PowerShell.
- Built as a folder instead of a single exe: faster start, less memory.
- Installer (Inno Setup) for the current user, with uninstaller.
- On first start the old v1.6 AutoHotkey script is stopped; settings are kept.

## 1.6

- Last version based on AutoHotkey v2.
