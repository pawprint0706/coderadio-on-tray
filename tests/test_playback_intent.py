from __future__ import annotations

from PySide6.QtCore import QObject

import coderadio_tray.app as app_module
from coderadio_tray.app import CodeRadioApp
from coderadio_tray.config import AppConfig
from coderadio_tray.metadata.client import StationSnapshot, TrackInfo


def _bare_app() -> CodeRadioApp:
    """Create an app state machine without starting mpv, timers, or tray UI."""
    app = CodeRadioApp.__new__(CodeRadioApp)
    QObject.__init__(app)
    return app


def test_stream_end_while_user_paused_does_not_reconnect() -> None:
    app = _bare_app()
    app._playback_requested = False
    reconnects: list[bool] = []
    app._schedule_reconnect = lambda: reconnects.append(True)

    app._on_stream_ended()

    assert reconnects == []


def test_stream_end_while_playing_still_reconnects() -> None:
    app = _bare_app()
    app._playback_requested = True
    reconnects: list[bool] = []
    app._schedule_reconnect = lambda: reconnects.append(True)

    app._on_stream_ended()

    assert reconnects == [True]


def test_pause_closes_live_stream_and_cancels_reconnect() -> None:
    app = _bare_app()
    app._playback_requested = True
    app._user_paused = False
    app._error = "Reconnecting in 2s..."
    commands: list[tuple[str, tuple[object, ...]]] = []
    reconnect_cancellations: list[bool] = []
    app._queue_player_cmd = lambda cmd, *args: commands.append((cmd, args))
    app._cancel_reconnect = lambda: reconnect_cancellations.append(True)
    app._update_ui = lambda: None

    app.toggle_playback()

    assert app._playback_requested is False
    assert app._user_paused is True
    assert app._error is None
    assert reconnect_cancellations == [True]
    assert commands == [("stop", ())]


def test_resume_from_pause_starts_a_fresh_live_stream() -> None:
    app = _bare_app()
    app._playback_requested = False
    app._user_paused = True
    app._pending_bitrate = "64"
    starts: list[bool] = []
    app._start_playback = lambda: starts.append(True)
    app._update_ui = lambda: None

    app.toggle_playback()

    assert app._playback_requested is True
    assert app._user_paused is False
    assert app._pending_bitrate is None
    assert starts == [True]


def test_reconnect_callback_cannot_restart_while_paused() -> None:
    app = _bare_app()
    app._playback_requested = False
    app._reconnect_timer = object()
    starts: list[bool] = []
    app._start_playback = lambda: starts.append(True)

    app._do_reconnect()

    assert app._reconnect_timer is None
    assert starts == []


def test_metadata_failure_does_not_replace_paused_status() -> None:
    app = _bare_app()
    app._user_paused = True
    app._error = None
    ui_updates: list[bool] = []
    app._update_ui = lambda: ui_updates.append(True)

    app._on_metadata_failed("network disconnected")

    assert app._error is None
    assert ui_updates == []


def test_bitrate_change_while_paused_does_not_start_playback(monkeypatch) -> None:
    app = _bare_app()
    app._playback_requested = False
    app._user_paused = True
    app._config = AppConfig(bitrate="128")
    app._snapshot = StationSnapshot(
        is_online=True,
        track=TrackInfo(),
        stream_128="https://example/radio.mp3",
        stream_64="https://example/low.mp3",
        listen_url="https://example/listen",
    )
    app._stream_url = app._snapshot.stream_128
    app._pending_bitrate = None
    starts: list[bool] = []
    app._start_playback = lambda: starts.append(True)
    app._update_ui = lambda: None
    monkeypatch.setattr(app_module, "save_config", lambda _config: None)

    app._on_bitrate("64")

    assert app._stream_url == "https://example/low.mp3"
    assert starts == []
