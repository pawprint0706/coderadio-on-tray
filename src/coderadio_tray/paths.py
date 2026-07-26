from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Directory that contains the running app (exe folder when frozen)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # src/coderadio_tray/paths.py → repo root
    return Path(__file__).resolve().parents[2]


def meipass_dir() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw).resolve() if raw else None


def mpv_binary_name() -> str:
    return "mpv.exe" if sys.platform == "win32" else "mpv"


def iter_mpv_candidates(configured: str = "mpv") -> list[Path]:
    """Ordered search paths for a bundled or configured mpv binary."""
    name = mpv_binary_name()
    out: list[Path] = []

    if configured and configured not in {"mpv", "mpv.exe"}:
        out.append(Path(configured))

    base = app_dir()
    out.extend(
        [
            base / "mpv" / name,
            base / name,
        ]
    )

    meipass = meipass_dir()
    if meipass is not None:
        out.extend(
            [
                meipass / "mpv" / name,
                meipass / name,
            ]
        )

    if not is_frozen():
        out.append(base / ".tools" / "mpv" / "extract" / name)

    return out
