from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QSystemTrayIcon

from coderadio_tray.ui.icons import _win_taskbar_is_light, make_tray_icon
from coderadio_tray.ui.popup import TrayPopup

logger = logging.getLogger(__name__)


class TrayController(QObject):
    def __init__(self, popup: TrayPopup, *, first_run: bool = False, on_hint_shown=None) -> None:
        super().__init__()
        self.popup = popup
        self.tray = QSystemTrayIcon(make_tray_icon(playing=False), self)
        self.tray.setToolTip("Code Radio")
        self.tray.activated.connect(self._on_activated)
        self.tray.messageClicked.connect(self._on_message_clicked)
        self._left_click_handler = lambda: None
        self._message_click_handler = None
        self._left_click_action = "toggle"
        self._hint_shown = not first_run
        self._on_hint_shown = on_hint_shown
        self._playing = False
        self._error = False
        self._error_blink_visible = True
        self._error_blink_timer = QTimer(self)
        self._error_blink_timer.setInterval(1000)
        self._error_blink_timer.timeout.connect(self._toggle_error_blink)

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
        self._refresh_icon()

    def _check_win_taskbar_theme(self) -> None:
        current = _win_taskbar_is_light()
        if current == self._win_taskbar_light:
            return
        self._win_taskbar_light = current
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        self.tray.setIcon(
            make_tray_icon(
                playing=self._playing,
                error=self._error,
                error_visible=self._error_blink_visible,
            )
        )

    def _toggle_error_blink(self) -> None:
        if not self._error:
            return
        self._error_blink_visible = not self._error_blink_visible
        self._refresh_icon()

    def show(self) -> None:
        self._refresh_icon()
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
            if self._on_hint_shown is not None:
                self._on_hint_shown()

    def hide(self) -> None:
        self._error_blink_timer.stop()
        self.tray.hide()

    def is_visible(self) -> bool:
        return self.tray.isVisible()

    def set_playing(self, playing: bool, *, error: bool = False) -> None:
        self._playing = playing
        error_changed = error != self._error
        self._error = error
        if error:
            if error_changed:
                self._error_blink_visible = True
            if not self._error_blink_timer.isActive():
                self._error_blink_timer.start()
        else:
            self._error_blink_timer.stop()
            self._error_blink_visible = False
        self._refresh_icon()
        self.popup.set_playing(playing)

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip(text)

    def set_left_click_action(self, action: str) -> None:
        self._left_click_action = action if action in {"toggle", "popup"} else "toggle"

    def show_message(self, title: str, message: str, on_click=None) -> None:
        self._message_click_handler = on_click
        self.tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            7000,
        )

    def _on_message_clicked(self) -> None:
        handler = self._message_click_handler
        self._message_click_handler = None
        if handler is not None:
            handler()

    def _popup_anchor(self) -> QPoint:
        # Anchor to the tray icon geometry so the popup opens at a fixed spot
        # under the icon (matching Windows) instead of at the click point, which
        # on the macOS menu bar drifts with the pixel the user happened to hit.
        geo = self.tray.geometry()
        if geo.isValid() and not geo.isNull():
            return QPoint(geo.center().x(), geo.y() + geo.height())
        return QCursor.pos()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Context:
            self.popup.popup_at(self._popup_anchor())
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._left_click_action == "popup":
                self.popup.popup_at(self._popup_anchor())
            else:
                self._left_click_handler()

    def on_left_click(self, handler) -> None:
        self._left_click_handler = handler
