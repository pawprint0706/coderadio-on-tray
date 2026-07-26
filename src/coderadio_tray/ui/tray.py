from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QSystemTrayIcon

from coderadio_tray.ui.icons import _win_taskbar_is_light, make_tray_icon
from coderadio_tray.ui.popup import TrayPopup

logger = logging.getLogger(__name__)


class TrayController(QObject):
    def __init__(self, popup: TrayPopup) -> None:
        super().__init__()
        self.popup = popup
        self.tray = QSystemTrayIcon(make_tray_icon(playing=False), self)
        self.tray.setToolTip("Code Radio")
        self.tray.activated.connect(self._on_activated)
        self._left_click_handler = lambda: None
        self._hint_shown = False
        self._playing = False
        self._error = False

        if sys.platform == "darwin":
            pass
        elif sys.platform == "win32":
            self._win_taskbar_light = _win_taskbar_is_light()
            self._win_theme_timer = QTimer(self)
            self._win_theme_timer.setInterval(2000)
            self._win_theme_timer.timeout.connect(self._check_win_taskbar_theme)
            self._win_theme_timer.start()
        else:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, _scheme: object = None) -> None:
        self.tray.setIcon(make_tray_icon(playing=self._playing, error=self._error))

    def _check_win_taskbar_theme(self) -> None:
        current = _win_taskbar_is_light()
        if current == self._win_taskbar_light:
            return
        self._win_taskbar_light = current
        self.tray.setIcon(make_tray_icon(playing=self._playing, error=self._error))

    def show(self) -> None:
        self.tray.setIcon(make_tray_icon(playing=self._playing, error=self._error))
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
        self._playing = playing
        self._error = error
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