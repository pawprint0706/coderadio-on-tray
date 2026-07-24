from __future__ import annotations

import ctypes
import sys


def hide_console_window() -> None:
    """Hide the console when launched via python.exe (tray-only app)."""
    if sys.platform != "win32":
        return
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
