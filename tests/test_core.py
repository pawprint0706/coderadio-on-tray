from __future__ import annotations

from coderadio_tray.config import AppConfig
from coderadio_tray.metadata.client import StationSnapshot, TrackInfo
from coderadio_tray.player.mpv_player import ui_volume_to_mpv


def test_config_clamp_volume_and_bitrate() -> None:
    cfg = AppConfig(volume=200, bitrate="999", poll_seconds=1).clamp()
    assert cfg.volume == 100
    assert cfg.bitrate == "128"
    assert cfg.poll_seconds == 5


def test_config_clamp_low() -> None:
    cfg = AppConfig(volume=-5, bitrate="64", poll_seconds=999).clamp()
    assert cfg.volume == 0
    assert cfg.bitrate == "64"
    assert cfg.poll_seconds == 120


def test_stream_for_bitrate() -> None:
    snap = StationSnapshot(
        is_online=True,
        track=TrackInfo(title="t", artist="a"),
        stream_128="https://example/radio.mp3",
        stream_64="https://example/low.mp3",
        listen_url="https://example/listen",
    )
    assert snap.stream_for_bitrate("64") == "https://example/low.mp3"
    assert snap.stream_for_bitrate("128") == "https://example/radio.mp3"
    assert snap.stream_for_bitrate("other") == "https://example/radio.mp3"


def test_stream_for_bitrate_falls_back_to_listen() -> None:
    snap = StationSnapshot(
        is_online=True,
        track=TrackInfo(),
        stream_128="",
        stream_64="",
        listen_url="https://example/listen",
    )
    assert snap.stream_for_bitrate("128") == "https://example/listen"


def test_ui_volume_to_mpv_curve() -> None:
    assert ui_volume_to_mpv(0) == 0.0
    assert ui_volume_to_mpv(100) == 100.0
    mid = ui_volume_to_mpv(50)
    assert 55.0 <= mid <= 65.0
    assert ui_volume_to_mpv(50) > 50.0


def test_end_file_intentional_reasons() -> None:
    intentional = {"stop", "quit", "redirect"}
    unexpected = {"eof", "error", "unknown"}
    assert intentional.isdisjoint(unexpected)
