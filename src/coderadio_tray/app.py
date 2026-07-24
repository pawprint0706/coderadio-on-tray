from __future__ import annotations

import logging
import os
import signal
import sys
import webbrowser

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from coderadio_tray.config import OFFICIAL_SITE, load_config, save_config
from coderadio_tray.metadata import MetadataClient, StationSnapshot, TrackInfo
from coderadio_tray.player import MpvNotFoundError, MpvPlayer
from coderadio_tray.ui import TrayController, TrayPopup
from coderadio_tray.ui.icons import make_tray_icon

logger = logging.getLogger(__name__)


class WorkerBridge(QObject):
    metadata_ready = Signal(object)
    metadata_failed = Signal(str)


class CodeRadioApp(QObject):
    def __init__(self, qt_app: QApplication) -> None:
        super().__init__()
        self._qt_app = qt_app
        self._config = load_config()
        self._client = MetadataClient()
        self._snapshot: StationSnapshot | None = None
        self._track = TrackInfo()
        self._stream_url = ""
        self._error: str | None = None
        self._auto_started = False

        self._player = MpvPlayer(mpv_path=self._config.mpv_path, volume=self._config.volume)

        self._bridge = WorkerBridge()
        self._bridge.metadata_ready.connect(self._on_metadata)
        self._bridge.metadata_failed.connect(self._on_metadata_failed)

        self._popup = TrayPopup()
        self._popup.set_volume(self._config.volume)
        self._popup.set_bitrate(self._config.bitrate)
        self._popup.play_pause_clicked.connect(self.toggle_playback)
        self._popup.volume_changed.connect(self._on_volume)
        self._popup.bitrate_changed.connect(self._on_bitrate)
        self._popup.open_site_clicked.connect(lambda: webbrowser.open(OFFICIAL_SITE))
        self._popup.quit_clicked.connect(self.quit)

        self._tray = TrayController(self._popup)
        self._tray.on_left_click(self.toggle_playback)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._config.poll_seconds * 1000)
        self._poll_timer.timeout.connect(self.refresh_metadata)
        self._poll_timer.start()

        self._update_ui()
        QTimer.singleShot(0, self.refresh_metadata)

    def show_tray(self) -> None:
        self._tray.show()
        if not self._tray.is_visible():
            QMessageBox.warning(
                None,
                "Code Radio Tray",
                "The tray icon could not be shown.\n\n"
                "Check Windows Settings → System → Notifications → "
                "Other system tray icons.\n\n"
                "Press Ctrl+C in the console or close this dialog and use Task Manager "
                "to end python.exe / mpv.exe.",
            )

    def refresh_metadata(self) -> None:
        import threading

        def work() -> None:
            try:
                snap = self._client.fetch()
                self._bridge.metadata_ready.emit(snap)
            except Exception as exc:
                logger.exception("metadata fetch failed")
                self._bridge.metadata_failed.emit(str(exc))

        threading.Thread(target=work, name="metadata-poll", daemon=True).start()

    @Slot(object)
    def _on_metadata(self, snapshot: object) -> None:
        assert isinstance(snapshot, StationSnapshot)
        self._snapshot = snapshot
        self._track = snapshot.track
        self._stream_url = snapshot.stream_for_bitrate(self._config.bitrate)
        self._error = None if snapshot.is_online else "Station offline"
        self._update_ui()
        if not self._auto_started and snapshot.is_online and self._stream_url:
            self._auto_started = True
            self._start_playback()

    @Slot(str)
    def _on_metadata_failed(self, message: str) -> None:
        self._error = message
        self._update_ui()

    def toggle_playback(self) -> None:
        try:
            if self._player.is_playing():
                self._player.pause()
            elif getattr(self._player, "_playing", False) and getattr(self._player, "_paused", False):
                self._player.resume()
            else:
                self._start_playback()
            self._error = None
        except Exception as exc:
            logger.exception("toggle failed")
            self._error = str(exc)
        self._update_ui()

    def _start_playback(self) -> None:
        if not self._stream_url:
            self._error = "No stream URL yet"
            self.refresh_metadata()
            self._update_ui()
            return
        try:
            self._player.play(self._stream_url)
            self._error = None
        except Exception as exc:
            logger.exception("playback failed")
            self._error = str(exc)
        self._update_ui()

    @Slot(int)
    def _on_volume(self, volume: int) -> None:
        self._config.volume = volume
        self._player.set_volume(volume)
        save_config(self._config)

    @Slot(str)
    def _on_bitrate(self, bitrate: str) -> None:
        if bitrate == self._config.bitrate:
            return
        was_playing = self._player.is_playing()
        self._config.bitrate = bitrate
        save_config(self._config)
        if self._snapshot:
            self._stream_url = self._snapshot.stream_for_bitrate(bitrate)
        if was_playing and self._stream_url:
            self._start_playback()
        else:
            self._update_ui()

    def _update_ui(self) -> None:
        playing = self._player.is_playing()
        track = self._track.display
        self._popup.set_track_text(track)
        if self._error:
            status = f"Error: {self._error}"
        elif playing:
            status = "Playing"
        elif getattr(self._player, "_paused", False):
            status = "Paused"
        else:
            status = "Stopped"
        self._popup.set_status(status)
        self._popup.set_playing(playing)
        self._tray.set_playing(playing, error=bool(self._error))
        tip = f"Code Radio\n{track}"
        if self._error:
            tip += f"\n{self._error}"
        self._tray.set_tooltip(tip)

    def quit(self) -> None:
        save_config(self._config)
        self._poll_timer.stop()
        self._popup.hide()
        self._tray.hide()
        try:
            self._player.shutdown()
        except Exception:
            logger.exception("player shutdown failed")
        try:
            self._client.close()
        except Exception:
            logger.exception("client close failed")
        self._qt_app.quit()


def _install_sigint_handler(qt_app: QApplication, app: CodeRadioApp) -> None:
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    # Allow Python signal delivery while Qt event loop runs.
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(400)
    qt_app._sigint_timer = timer  # type: ignore[attr-defined]


def run(*, hide_console: bool | None = None) -> int:
    if hide_console is None:
        hide_console = os.environ.get("CODERADIO_TRAY_CONSOLE", "").lower() not in {
            "1",
            "true",
            "yes",
        }

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if hide_console and sys.platform == "win32":
        from coderadio_tray.platform_win import hide_console_window

        hide_console_window()
        logger.info("console hidden (set CODERADIO_TRAY_CONSOLE=1 to keep it)")

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    qt_app.setApplicationName("Code Radio Tray")
    qt_app.setOrganizationName("coderadio-on-tray")
    qt_app.setApplicationDisplayName("Code Radio Tray")
    qt_app.setWindowIcon(make_tray_icon(playing=False))

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Code Radio Tray", "System tray is not available on this desktop.")
        return 1

    try:
        app = CodeRadioApp(qt_app)
    except MpvNotFoundError as exc:
        QMessageBox.critical(None, "Code Radio Tray", str(exc))
        return 1

    qt_app._coderadio_app = app  # type: ignore[attr-defined]
    _install_sigint_handler(qt_app, app)

    # Windows: show tray only after the event loop has started.
    QTimer.singleShot(0, app.show_tray)

    if not hide_console:
        print("Code Radio Tray running. Ctrl+C to quit.", flush=True)

    return qt_app.exec()
