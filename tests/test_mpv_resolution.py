from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QObject

from coderadio_tray import paths
from coderadio_tray.player.mpv_player import MpvNotFoundError, MpvPlayer
from coderadio_tray.player.worker import PlayerWorker


def test_resolver_skips_broken_candidate(monkeypatch, tmp_path) -> None:
    broken = tmp_path / "broken-mpv"
    working = tmp_path / "working-mpv"
    broken.touch()
    working.touch()
    monkeypatch.setattr(paths, "iter_mpv_candidates", lambda _configured: [broken, working])
    monkeypatch.setattr(
        MpvPlayer,
        "_probe_mpv",
        staticmethod(
            lambda candidate: (
                (False, "missing dylib") if candidate == broken else (True, "mpv v0.41.0")
            )
        ),
    )

    assert MpvPlayer._resolve_mpv("mpv") == str(working)


def test_resolver_reports_rejected_candidates(monkeypatch, tmp_path) -> None:
    broken = tmp_path / "broken-mpv"
    broken.touch()
    monkeypatch.setattr(paths, "iter_mpv_candidates", lambda _configured: [broken])
    monkeypatch.setattr(
        MpvPlayer,
        "_probe_mpv",
        staticmethod(lambda _candidate: (False, "missing dylib")),
    )

    with pytest.raises(MpvNotFoundError, match="missing dylib"):
        MpvPlayer._resolve_mpv("mpv")


def test_worker_emits_playback_failure(qapp) -> None:
    class BrokenPlayer:
        @staticmethod
        def play(_url: str) -> None:
            raise RuntimeError("mpv exited during startup")

    worker = PlayerWorker.__new__(PlayerWorker)
    QObject.__init__(worker)
    worker._player = BrokenPlayer()
    failures: list[str] = []
    worker.playback_failed.connect(failures.append)

    worker._on_play("https://example/radio.mp3")

    assert failures == ["mpv exited during startup"]


def test_packaging_policy_pins_windows_checksum_and_macos_formula() -> None:
    policy_path = Path(__file__).resolve().parents[1] / "packaging" / "mpv-versions.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))

    assert len(policy["windows"]["sha256"]) == 64
    assert policy["windows"]["url"].endswith(policy["windows"]["archive"])
    assert policy["macos"]["formula_version"]
