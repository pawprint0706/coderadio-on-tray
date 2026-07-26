from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from coderadio_tray.player.mpv_player import MpvPlayer

logger = logging.getLogger(__name__)


class PlayerWorker(QObject):
    state_changed = Signal()
    stream_ended = Signal()
    play_request = Signal(str)
    pause_request = Signal()
    resume_request = Signal()
    stop_request = Signal()
    set_volume_request = Signal(int)
    shutdown_request = Signal()

    def __init__(self, mpv_path: str = "mpv", volume: int = 70) -> None:
        super().__init__()
        self._player = MpvPlayer(mpv_path=mpv_path, volume=volume)
        self._player.set_event_callback(self._on_mpv_event)

        self.play_request.connect(self._on_play)
        self.pause_request.connect(self._on_pause)
        self.resume_request.connect(self._on_resume)
        self.stop_request.connect(self._on_stop)
        self.set_volume_request.connect(self._on_set_volume)
        self.shutdown_request.connect(self._on_shutdown)

    def _on_mpv_event(self, event: str, msg: dict) -> None:
        if event != "end-file":
            return
        reason = str(msg.get("reason") or "unknown")
        # Bitrate switches use loadfile replace, which ends the previous file
        # with reason "stop". Reconnecting on that creates an interrupt loop.
        if reason in {"stop", "quit", "redirect"}:
            logger.info("ignoring intentional end-file (%s)", reason)
            return
        logger.info("unexpected end-file (%s), requesting reconnect", reason)
        self.stream_ended.emit()

    @Slot(str)
    def _on_play(self, url: str) -> None:
        try:
            self._player.play(url)
        except Exception:
            logger.exception("play failed")
        self.state_changed.emit()

    @Slot()
    def _on_pause(self) -> None:
        self._player.pause()
        self.state_changed.emit()

    @Slot()
    def _on_resume(self) -> None:
        self._player.resume()
        self.state_changed.emit()

    @Slot(int)
    def _on_set_volume(self, volume: int) -> None:
        self._player.set_volume(volume)

    @Slot()
    def _on_stop(self) -> None:
        self._player.stop()
        self.state_changed.emit()

    @Slot()
    def _on_shutdown(self) -> None:
        self._player.shutdown()

    def shutdown(self) -> None:
        self._on_shutdown()

    def is_playing(self) -> bool:
        return self._player.is_playing()

    def is_paused(self) -> bool:
        return self._player.is_paused()

    def get_volume(self) -> int:
        return self._player.get_volume()

    def is_alive(self) -> bool:
        return self._player.is_alive()
