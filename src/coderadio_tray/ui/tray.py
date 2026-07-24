from __future__ import annotations

import logging

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QSystemTrayIcon

from coderadio_tray.ui.icons import make_tray_icon
from coderadio_tray.ui.popup import TrayPopup

logger = logging.getLogger(__name__)


class TrayController:
    def __init__(self, popup: TrayPopup) -> None:
        self.popup = popup
        self.tray = QSystemTrayIcon(make_tray_icon(playing=False))
        self.tray.setToolTip("Code Radio")
        self.tray.activated.connect(self._on_activated)
        self._left_click_handler = lambda: None
        self._hint_shown = False

    def show(self) -> None:
        self.tray.setIcon(make_tray_icon(playing=False))
        self.tray.show()
        if not self.tray.isVisible():
            logger.error("system tray icon is not visible after show()")
            return
        if not self._hint_shown:
            self._hint_shown = True
            self.tray.showMessage(
                "Code Radio Tray",
                "Running in the notification area. If hidden, open the ^ overflow menu.",
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )

    def hide(self) -> None:
        self.tray.hide()

    def is_visible(self) -> bool:
        return self.tray.isVisible()

    def set_playing(self, playing: bool, *, error: bool = False) -> None:
        self.tray.setIcon(make_tray_icon(playing=playing, error=error))
        self.popup.set_playing(playing)

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip(text)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.popup.popup_at(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._left_click_handler()

    def on_left_click(self, handler) -> None:
        self._left_click_handler = handler
