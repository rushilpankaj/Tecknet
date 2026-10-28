"""Launcher without a console window (pythonw) and entry point for PyInstaller."""

import sys

from tecknet_control.__main__ import main

sys.exit(main())
