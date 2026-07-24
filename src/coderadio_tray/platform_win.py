from __future__ import annotations

import ctypes
import os
import sys


def hide_console_window() -> None:
    """Hide the console when launched via python.exe (tray-only app).

    Only hides if the console belongs exclusively to this process,
    so that a user's terminal (e.g. PowerShell) is not hidden.
    """
    if sys.platform != "win32":
        return
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if not hwnd:
        return

    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value != os.getpid():
        return

    process_list = (ctypes.c_ulong * 2)()
    count = ctypes.windll.kernel32.GetConsoleProcessList(process_list, 2)
    if count > 1:
        return

    ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
