from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import webbrowser

import httpx
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from coderadio_tray import __version__
from coderadio_tray.config import OFFICIAL_SITE, USER_AGENT, load_config, save_config
from coderadio_tray.metadata import MetadataClient, StationSnapshot, TrackInfo
from coderadio_tray.player import MpvNotFoundError, PlayerWorker
from coderadio_tray.single_instance import try_acquire as try_acquire_single_instance
from coderadio_tray.startup import set_login_startup
from coderadio_tray.ui import TrayController, TrayPopup
from coderadio_tray.ui.icons import make_app_icon
from coderadio_tray.updates import ReleaseInfo, fetch_latest_release, is_newer_version

logger = logging.getLogger(__name__)


class WorkerBridge(QObject):
    metadata_ready = Signal(object)
    metadata_failed = Signal(str)
    artwork_ready = Signal(str, object)
    update_ready = Signal(object)
    update_failed = Signal(str)


def _run_in_thread(target):
    threading.Thread(target=target, daemon=True).start()


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
        self._playback_error: str | None = None
        self._auto_started = False
        # Keep the user's playback intent separate from mpv's transient state.
        # A paused live stream can eventually end at the server/cache layer;
        # that must not turn a user pause into an automatic reconnect/play.
        self._playback_requested = False
        self._user_paused = False
        self._reconnect_count = 0
        self._reconnect_timer: QTimer | None = None
        self._pending_bitrate: str | None = None
        self._art_url = ""
        self._art_data: bytes | None = None
        self._update_check_in_progress = False

        self._player_thread = QThread(self)
        self._player_worker = PlayerWorker(
            mpv_path=self._config.mpv_path, volume=self._config.volume
        )
        self._player_worker.moveToThread(self._player_thread)
        self._player_worker.state_changed.connect(self._on_player_state_changed)
        self._player_worker.stream_ended.connect(self._on_stream_ended)
        self._player_worker.playback_failed.connect(self._on_playback_failed)
        self._player_thread.start()

        self._bridge = WorkerBridge()
        self._bridge.metadata_ready.connect(self._on_metadata)
        self._bridge.metadata_failed.connect(self._on_metadata_failed)
        self._bridge.artwork_ready.connect(self._on_artwork_ready)
        self._bridge.update_ready.connect(self._on_update_ready)
        self._bridge.update_failed.connect(self._on_update_failed)

        self._popup = TrayPopup()
        self._popup.set_volume(self._config.volume)
        self._popup.set_bitrate(self._config.bitrate)
        self._popup.set_settings(self._config)
        self._popup.set_album_art_visible(self._config.show_album_art)
        self._popup.set_listener_count_visible(self._config.show_listener_count)
        self._popup.play_pause_clicked.connect(self.toggle_playback)
        self._popup.volume_changed.connect(self._on_volume)
        self._popup.volume_released.connect(self._save_volume)
        self._popup.bitrate_changed.connect(self._on_bitrate)
        self._popup.open_site_clicked.connect(lambda: webbrowser.open(OFFICIAL_SITE))
        self._popup.quit_clicked.connect(self.quit)
        self._popup.settings_changed.connect(self._on_settings_changed)

        self._tray = TrayController(
            self._popup,
            first_run=not self._config.first_run_hint_shown,
            on_hint_shown=self._mark_hint_shown,
        )
        self._tray.on_left_click(self.toggle_playback)
        self._tray.set_left_click_action(self._config.tray_click_action)

        if self._config.auto_start_login:
            self._sync_login_startup(True, show_error=False)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._config.poll_seconds * 1000)
        self._poll_timer.timeout.connect(self.refresh_metadata)
        self._poll_timer.start()

        self._update_ui()
        QTimer.singleShot(0, self.refresh_metadata)
        if self._config.notify_updates:
            QTimer.singleShot(1500, self._check_for_updates)

    def show_tray(self) -> None:
        self._tray.show()
        if not self._tray.is_visible():
            QMessageBox.warning(
                None,
                "Code Radio Tray",
                "The tray icon could not be shown.\n\n"
                "Check Windows Settings \u2192 System \u2192 Notifications \u2192 "
                "Other system tray icons.\n\n"
                "Press Ctrl+C in the console or close this dialog and use Task Manager "
                "to end python.exe / mpv.exe.",
            )

    def refresh_metadata(self) -> None:
        _run_in_thread(self._fetch_metadata)

    def _fetch_metadata(self) -> None:
        try:
            snap = self._client.fetch()
            self._bridge.metadata_ready.emit(snap)
        except Exception as exc:
            logger.exception("metadata fetch failed")
            self._bridge.metadata_failed.emit(str(exc))

    @Slot(object)
    def _on_metadata(self, snapshot: object) -> None:
        assert isinstance(snapshot, StationSnapshot)
        self._snapshot = snapshot
        self._track = snapshot.track
        self._stream_url = snapshot.stream_for_bitrate(self._config.bitrate)
        self._popup.set_listener_count(snapshot.listeners_current)
        self._update_artwork(snapshot.track.art_url)
        self._error = None if snapshot.is_online else "Station offline"
        self._update_ui()

        if not snapshot.is_online:
            if self._player_worker.is_playing() or self._player_worker.is_paused():
                self._queue_player_cmd("stop")
            return

        if self._pending_bitrate:
            self._apply_pending_bitrate()

        if not self._auto_started and self._stream_url:
            self._auto_started = True
            if self._config.auto_play:
                self._playback_requested = True
                self._start_playback()

    @Slot(str)
    def _on_metadata_failed(self, message: str) -> None:
        if self._user_paused:
            logger.info("metadata fetch failed while paused: %s", message)
            return
        self._error = message
        self._update_ui()

    @Slot()
    def _on_player_state_changed(self) -> None:
        self._update_ui()

    @Slot(str)
    def _on_playback_failed(self, message: str) -> None:
        if not self._playback_requested:
            return
        self._playback_requested = False
        self._user_paused = False
        self._cancel_reconnect()
        self._playback_error = f"Playback failed: {message}"
        self._update_ui()

    def _update_artwork(self, url: str) -> None:
        url = url.strip()
        if url == self._art_url:
            return
        self._art_url = url
        self._art_data = None
        self._popup.set_album_art(None)
        if self._config.show_album_art and url:
            _run_in_thread(lambda: self._fetch_artwork(url))

    def _fetch_artwork(self, url: str) -> None:
        try:
            response = httpx.get(
                url,
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            if len(response.content) > 5 * 1024 * 1024:
                raise ValueError("album artwork exceeds 5 MB")
            self._bridge.artwork_ready.emit(url, response.content)
        except Exception:
            logger.info("album artwork fetch failed: %s", url, exc_info=True)

    @Slot(str, object)
    def _on_artwork_ready(self, url: str, data: object) -> None:
        if url != self._art_url or not isinstance(data, bytes):
            return
        self._art_data = data
        if self._config.show_album_art:
            self._popup.set_album_art(data)

    @Slot()
    def _on_stream_ended(self) -> None:
        if not self._playback_requested:
            logger.info("stream ended while playback was not requested; staying paused")
            return
        logger.info("stream ended, scheduling reconnect")
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if not self._playback_requested:
            return
        if self._reconnect_timer and self._reconnect_timer.isActive():
            return
        delay = min(2**self._reconnect_count, 30)
        self._reconnect_count += 1
        logger.info("reconnect in %ds (attempt %d)", delay, self._reconnect_count)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)
        self._reconnect_timer.start(delay * 1000)
        self._error = f"Reconnecting in {delay}s..."
        self._update_ui()

    def _cancel_reconnect(self) -> None:
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()
            self._reconnect_timer = None
        self._reconnect_count = 0

    def _do_reconnect(self) -> None:
        self._reconnect_timer = None
        if not self._playback_requested:
            return
        if self._stream_url:
            self._start_playback()
        else:
            self.refresh_metadata()

    def _queue_player_cmd(self, cmd: str, *args) -> None:
        signal_map = {
            "play": (self._player_worker.play_request, args[0] if args else ""),
            "pause": (self._player_worker.pause_request, None),
            "resume": (self._player_worker.resume_request, None),
            "stop": (self._player_worker.stop_request, None),
            "set_volume": (self._player_worker.set_volume_request, args[0] if args else 0),
        }
        entry = signal_map.get(cmd)
        if entry:
            sig, val = entry
            if val is not None:
                sig.emit(val)
            else:
                sig.emit()

    def toggle_playback(self) -> None:
        try:
            if self._playback_requested:
                # For a live stream, pause means closing the current connection.
                # Resuming later starts at the live edge and cannot inherit a
                # server/cache timeout from an indefinitely paused connection.
                self._playback_requested = False
                self._user_paused = True
                self._cancel_reconnect()
                self._error = None
                self._queue_player_cmd("stop")
            elif self._user_paused:
                self._playback_requested = True
                self._user_paused = False
                self._pending_bitrate = None
                self._start_playback()
            elif self._stream_url:
                self._playback_requested = True
                self._user_paused = False
                self._start_playback()
            else:
                self._error = "No stream URL yet"
                self.refresh_metadata()
        except Exception as exc:
            logger.exception("toggle failed")
            self._error = str(exc)
        self._update_ui()

    def _start_playback(self) -> None:
        if not self._playback_requested:
            return
        if not self._stream_url:
            self._error = "No stream URL yet"
            self.refresh_metadata()
            self._update_ui()
            return
        self._cancel_reconnect()
        self._error = None
        self._playback_error = None
        self._queue_player_cmd("play", self._stream_url)
        self._update_ui()

    @Slot(int)
    def _on_volume(self, volume: int) -> None:
        self._config.volume = volume
        self._queue_player_cmd("set_volume", volume)

    def _save_volume(self) -> None:
        save_config(self._config)

    @Slot(object)
    def _on_settings_changed(self, settings: object) -> None:
        if not isinstance(settings, dict):
            return
        old_login_startup = self._config.auto_start_login
        old_notify_updates = self._config.notify_updates
        for name in (
            "auto_start_login",
            "auto_play",
            "notify_updates",
            "show_album_art",
            "show_listener_count",
            "tray_click_action",
        ):
            if name in settings:
                setattr(self._config, name, settings[name])
        self._config.clamp()

        if self._config.auto_start_login != old_login_startup and not self._sync_login_startup(
            self._config.auto_start_login, show_error=True
        ):
            self._config.auto_start_login = old_login_startup
            self._popup.set_settings(self._config)

        self._popup.set_album_art_visible(self._config.show_album_art)
        if self._config.show_album_art:
            if self._art_data is not None:
                self._popup.set_album_art(self._art_data)
            elif self._art_url:
                _run_in_thread(lambda: self._fetch_artwork(self._art_url))
        self._popup.set_listener_count_visible(self._config.show_listener_count)
        self._tray.set_left_click_action(self._config.tray_click_action)
        save_config(self._config)

        if self._config.notify_updates and not old_notify_updates:
            self._check_for_updates()

    def _sync_login_startup(self, enabled: bool, *, show_error: bool) -> bool:
        try:
            set_login_startup(enabled)
            if show_error:
                state = "enabled" if enabled else "disabled"
                self._popup.set_settings_status(f"Login startup {state}.")
            return True
        except Exception as exc:
            logger.exception("could not update login startup")
            if show_error:
                self._popup.set_settings_status(f"Could not update login startup: {exc}")
            return False

    def _check_for_updates(self) -> None:
        if self._update_check_in_progress or not self._config.notify_updates:
            return
        self._update_check_in_progress = True
        self._popup.set_settings_status("Checking for updates...")
        _run_in_thread(self._fetch_update)

    def _fetch_update(self) -> None:
        try:
            self._bridge.update_ready.emit(fetch_latest_release())
        except Exception as exc:
            logger.info("release check failed", exc_info=True)
            self._bridge.update_failed.emit(str(exc))

    @Slot(object)
    def _on_update_ready(self, release: object) -> None:
        self._update_check_in_progress = False
        if not self._config.notify_updates or not isinstance(release, ReleaseInfo):
            return
        if is_newer_version(release.version, __version__):
            self._popup.set_settings_status(
                f"Version {release.version} is available at GitHub Releases."
            )
            self._tray.show_message(
                "Code Radio Tray update available",
                f"Version {release.version} is available. Open Settings or GitHub Releases.",
                on_click=lambda: webbrowser.open(release.url),
            )
        else:
            self._popup.set_settings_status(f"Code Radio Tray {__version__} is up to date.")

    @Slot(str)
    def _on_update_failed(self, message: str) -> None:
        self._update_check_in_progress = False
        if self._config.notify_updates:
            self._popup.set_settings_status(f"Could not check for updates: {message}")

    @Slot(str)
    def _on_bitrate(self, bitrate: str) -> None:
        if bitrate == self._config.bitrate:
            return
        self._config.bitrate = bitrate
        if self._snapshot:
            self._stream_url = self._snapshot.stream_for_bitrate(bitrate)
        save_config(self._config)
        if self._playback_requested and self._stream_url:
            self._pending_bitrate = None
            self._start_playback()
        elif self._stream_url:
            self._pending_bitrate = bitrate
            self._update_ui()
        else:
            self._update_ui()

    def _apply_pending_bitrate(self) -> None:
        if not self._pending_bitrate or not self._snapshot:
            return
        self._stream_url = self._snapshot.stream_for_bitrate(self._pending_bitrate)
        self._pending_bitrate = None
        save_config(self._config)

    def _update_ui(self) -> None:
        playing = self._player_worker.is_playing()
        paused = self._user_paused
        track = self._track.display
        self._popup.set_track_text(track)
        error = self._playback_error or self._error
        if error:
            status = f"Error: {error}"
        elif playing:
            status = "Playing"
        elif paused:
            status = "Paused"
        else:
            status = "Stopped"
        self._popup.set_status(status)
        # During a reconnect the requested action is still "playing", so the
        # button remains Pause and can be used to cancel the retry loop.
        self._popup.set_playing(self._playback_requested)
        self._tray.set_playing(playing, error=bool(error))
        tip = f"Code Radio\n{track}"
        if error:
            tip += f"\n{error}"
        self._tray.set_tooltip(tip)

    def quit(self) -> None:
        save_config(self._config)
        self._poll_timer.stop()
        self._popup.hide()
        self._tray.hide()
        if self._player_thread.isRunning():
            self._player_worker.shutdown()
            self._player_thread.quit()
            self._player_thread.wait(2000)
        try:
            self._client.close()
        except Exception:
            logger.exception("client close failed")
        self._qt_app.quit()

    def _mark_hint_shown(self) -> None:
        self._config.first_run_hint_shown = True
        save_config(self._config)


def _install_sigint_handler(qt_app: QApplication, app: CodeRadioApp) -> None:
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(400)
    qt_app._sigint_timer = timer


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

    instance_lock = try_acquire_single_instance()
    if instance_lock is None:
        QMessageBox.information(
            None,
            "Code Radio Tray",
            "Code Radio Tray is already running.\n\n"
            "Look for the icon in the system tray / menu bar.",
        )
        return 0
    qt_app._single_instance_lock = instance_lock

    if sys.platform == "darwin":
        from coderadio_tray.platform_mac import hide_dock_icon

        hide_dock_icon()
    qt_app.setApplicationName("Code Radio Tray")
    qt_app.setOrganizationName("coderadio-on-tray")
    qt_app.setApplicationDisplayName("Code Radio Tray")
    qt_app.setWindowIcon(make_app_icon())

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None, "Code Radio Tray", "System tray is not available on this desktop."
        )
        return 1

    try:
        app = CodeRadioApp(qt_app)
    except MpvNotFoundError as exc:
        QMessageBox.critical(None, "Code Radio Tray", str(exc))
        return 1

    qt_app._coderadio_app = app
    _install_sigint_handler(qt_app, app)

    QTimer.singleShot(0, app.show_tray)

    if not hide_console:
        print("Code Radio Tray running. Ctrl+C to quit.", flush=True)

    return qt_app.exec()
