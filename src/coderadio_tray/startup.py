from __future__ import annotations

import contextlib
import plistlib
import subprocess
import sys
from pathlib import Path

from coderadio_tray.paths import is_frozen

_WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_NAME = "CodeRadioTray"
_MAC_LABEL = "org.coderadio-on-tray.app"


def startup_arguments() -> list[str]:
    if is_frozen():
        return [str(Path(sys.executable).resolve())]
    return [str(Path(sys.executable).resolve()), "-m", "coderadio_tray"]


def mac_launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_MAC_LABEL}.plist"


def set_login_startup(enabled: bool) -> None:
    if sys.platform == "win32":
        _set_windows_login_startup(enabled)
        return
    if sys.platform == "darwin":
        _set_macos_login_startup(enabled)
        return
    if enabled:
        raise RuntimeError("Login startup is currently supported on Windows and macOS only")


def _set_windows_login_startup(enabled: bool) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WINDOWS_RUN_KEY) as key:
        if enabled:
            command = subprocess.list2cmdline(startup_arguments())
            winreg.SetValueEx(key, _STARTUP_NAME, 0, winreg.REG_SZ, command)
        else:
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, _STARTUP_NAME)


def _set_macos_login_startup(enabled: bool) -> None:
    path = mac_launch_agent_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": _MAC_LABEL,
        "ProgramArguments": startup_arguments(),
        "RunAtLoad": True,
        "ProcessType": "Interactive",
    }
    path.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True))
