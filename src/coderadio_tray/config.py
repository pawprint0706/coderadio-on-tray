from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "coderadio-on-tray"
NOWPLAYING_URL = "https://coderadio-admin-v2.freecodecamp.org/api/nowplaying/coderadio"
OFFICIAL_SITE = "https://coderadio.freecodecamp.org/"
USER_AGENT = f"{APP_NAME}/0.1.0 (+unofficial; {OFFICIAL_SITE})"
DEFAULT_POLL_SECONDS = 15


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    volume: int = 70
    bitrate: str = "128"  # "128" or "64"
    poll_seconds: int = DEFAULT_POLL_SECONDS
    mpv_path: str = "mpv"
    first_run_hint_shown: bool = False

    def clamp(self) -> AppConfig:
        self.volume = max(0, min(100, int(self.volume)))
        if self.bitrate not in {"128", "64"}:
            self.bitrate = "128"
        self.poll_seconds = max(5, min(120, int(self.poll_seconds)))
        self.first_run_hint_shown = bool(self.first_run_hint_shown)
        return self


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig().clamp()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in AppConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return AppConfig(**filtered).clamp()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return AppConfig().clamp()


def save_config(config: AppConfig) -> None:
    config.clamp()
    path = config_path()
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
