from __future__ import annotations

import sys
from pathlib import Path

from coderadio_tray import paths


def test_iter_mpv_candidates_non_frozen(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    name = paths.mpv_binary_name()
    cands = paths.iter_mpv_candidates("mpv")
    assert cands, "expected at least one candidate"
    base = Path(__file__).resolve().parents[1]
    # Non-frozen build looks next to the repo root and in .tools/mpv/extract.
    assert (base / "mpv" / name) in cands
    assert (base / name) in cands
    assert (base / ".tools" / "mpv" / "extract" / name) in cands
    # No MEIPASS-derived paths when not frozen.
    assert not any("MEIPASS" in str(c) or "_MEIPASS" in str(c) for c in cands)


def test_iter_mpv_candidates_custom_path_first(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    custom = tmp_path / "custom-mpv"
    cands = paths.iter_mpv_candidates(str(custom))
    assert cands[0] == custom


def test_iter_mpv_candidates_frozen(monkeypatch, tmp_path):
    exe_dir = tmp_path / "frozen-app"
    exe_dir.mkdir()
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "CodeRadioTray"), raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    name = paths.mpv_binary_name()
    cands = paths.iter_mpv_candidates("mpv")
    assert (exe_dir / "mpv" / name) in cands
    assert (exe_dir / name) in cands
    assert (meipass / "mpv" / name) in cands
    assert (meipass / name) in cands
    # Frozen builds must not probe the dev-only .tools path.
    assert not any(".tools" in str(c) for c in cands)


def test_mpv_binary_name_per_platform():
    name = paths.mpv_binary_name()
    if sys.platform == "win32":
        assert name == "mpv.exe"
    else:
        assert name == "mpv"
