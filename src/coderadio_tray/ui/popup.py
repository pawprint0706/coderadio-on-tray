from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from coderadio_tray import platform_mac
from coderadio_tray.config import AppConfig

# Non-macOS Qt.Popup windows need to swallow the tray interaction briefly.
OUTSIDE_CLICK_GUARD_MS = 300
# On Windows/Linux the popup grabs the mouse, so a tray click's press auto-
# closes it (Qt.Popup) and the same click's release then reaches the tray and
# emits activated(Trigger). If that tail activation reopened the popup, the
# toggle could never close it. Treat activations inside this window after an
# outside-click hide as the tail of that same click instead of a new open.
AUTO_CLOSE_TAIL_MS = 500
PANEL_RADIUS = 12
SHADOW_MARGIN = 10
POPUP_WIDTH = 300


class TrayPopup(QWidget):
    """Non-modal popup anchored near the tray / cursor."""

    play_pause_clicked = Signal()
    volume_changed = Signal(int)
    volume_released = Signal()
    bitrate_changed = Signal(str)
    open_site_clicked = Signal()
    quit_clicked = Signal()
    settings_changed = Signal(object)
    _outside_clicked = Signal()

    def __init__(self) -> None:
        window_type = Qt.WindowType.Tool if sys.platform == "darwin" else Qt.WindowType.Popup
        super().__init__(
            None,
            window_type | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(POPUP_WIDTH + 2 * SHADOW_MARGIN)
        self._ignore_outside_until = 0.0
        self._mouse_monitor = None
        self._last_anchor = None
        self._loading_settings = False
        self._auto_closed_at = 0.0
        self._programmatic_hide = False
        self._album_art_enabled = True
        self._album_art_has_image = False
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self._outside_clicked.connect(self._on_global_mouse_down)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN, SHADOW_MARGIN)
        outer.setSpacing(0)

        self._panel = QFrame(self)
        self._panel.setObjectName("panel")
        shadow = QGraphicsDropShadowEffect(self._panel)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self._panel.setGraphicsEffect(shadow)
        outer.addWidget(self._panel)

        self._album_art = QLabel("No Album Art")
        self._album_art.setObjectName("album_art")
        self._album_art.setFixedSize(180, 180)
        self._album_art.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._track = QLabel("Code Radio")
        self._track.setObjectName("track_label")
        self._track.setWordWrap(True)

        self._listeners = QLabel("Listeners: 0")
        self._listeners.setObjectName("listeners_label")

        self._status = QLabel("Stopped")
        self._status.setObjectName("status_label")

        self._play_btn = QPushButton("Play")
        self._play_btn.clicked.connect(self.play_pause_clicked.emit)

        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(70)
        self._volume.valueChanged.connect(self.volume_changed.emit)
        self._volume.sliderReleased.connect(self.volume_released.emit)

        self._vol_label = QLabel("70%")
        self._vol_label.setFixedWidth(36)

        self._bitrate = QComboBox()
        self._bitrate.addItem("128 kbps", "128")
        self._bitrate.addItem("64 kbps", "64")
        self._bitrate.currentIndexChanged.connect(self._on_bitrate)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.clicked.connect(self.show_settings_page)
        self._site_btn = QPushButton("Site")
        self._site_btn.clicked.connect(self.open_site_clicked.emit)
        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(self.quit_clicked.emit)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Vol"))
        vol_row.addWidget(self._volume, stretch=1)
        vol_row.addWidget(self._vol_label)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._bitrate)

        foot = QHBoxLayout()
        foot.addWidget(self._settings_btn)
        foot.addWidget(self._site_btn)
        foot.addStretch(1)
        foot.addWidget(self._quit_btn)

        self._playback_page = QWidget()
        playback_root = QVBoxLayout(self._playback_page)
        playback_root.setContentsMargins(0, 0, 0, 0)
        playback_root.setSpacing(8)
        playback_root.addWidget(self._album_art, alignment=Qt.AlignmentFlag.AlignHCenter)
        playback_root.addWidget(self._track)
        playback_root.addWidget(self._listeners)
        playback_root.addWidget(self._status)
        playback_root.addLayout(vol_row)
        playback_root.addLayout(btn_row)
        playback_root.addLayout(foot)

        self._auto_start_login = QCheckBox("Start automatically at login")
        self._auto_play = QCheckBox("Play automatically when the app starts")
        self._notify_updates = QCheckBox("Notify me about new releases")
        self._show_album_art = QCheckBox("Show album art")
        self._show_listener_count = QCheckBox("Show listener count")
        for checkbox in (
            self._auto_start_login,
            self._auto_play,
            self._notify_updates,
            self._show_album_art,
            self._show_listener_count,
        ):
            checkbox.toggled.connect(self._emit_settings)

        self._tray_click_action = QComboBox()
        self._tray_click_action.addItem("Play / Pause", "toggle")
        self._tray_click_action.addItem("Open / close popup", "popup")
        self._tray_click_action.currentIndexChanged.connect(self._emit_settings)

        self._settings_status = QLabel("")
        self._settings_status.setObjectName("settings_status")
        self._settings_status.setWordWrap(True)
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.show_playback_page)

        self._settings_page = QWidget()
        settings_root = QVBoxLayout(self._settings_page)
        # macOS applies asymmetric native layout-item margins to controls.
        # Use widget rectangles with matching explicit side margins so the
        # visible right edge aligns with the existing left inset.
        settings_root.setContentsMargins(2, 0, 2, 0)
        settings_root.setSpacing(8)
        settings_title = QLabel("Settings")
        settings_title.setObjectName("settings_title")
        tray_click_label = QLabel("Tray / menu-bar left click")
        for widget in (
            settings_title,
            self._auto_start_login,
            self._auto_play,
            self._show_album_art,
            self._show_listener_count,
            tray_click_label,
            self._tray_click_action,
            self._notify_updates,
            self._settings_status,
            self._back_btn,
        ):
            widget.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
        settings_root.addWidget(settings_title)
        settings_root.addWidget(self._auto_start_login)
        settings_root.addWidget(self._auto_play)
        settings_root.addWidget(self._show_album_art)
        settings_root.addWidget(self._show_listener_count)
        settings_root.addWidget(tray_click_label)
        settings_root.addWidget(self._tray_click_action)
        settings_root.addWidget(self._notify_updates)
        settings_root.addWidget(self._settings_status)
        settings_root.addStretch(1)
        settings_root.addWidget(self._back_btn)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._playback_page)
        self._pages.addWidget(self._settings_page)

        root = QVBoxLayout(self._panel)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)
        root.addWidget(self._pages)

        self._volume.valueChanged.connect(lambda v: self._vol_label.setText(f"{v}%"))

        self._apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._apply_theme)
        QTimer.singleShot(0, self._resize_current_page)

    def _apply_theme(self, scheme: object = None) -> None:
        if scheme is None:
            scheme = QGuiApplication.styleHints().colorScheme()
        dark = scheme == Qt.ColorScheme.Dark
        if dark:
            bg, fg, border = "#1e1e1e", "#f0f0f0", "#5a5a5a"
            btn_bg, btn_hover = "#2d2d2d", "#3a3a3a"
            status_color = "#9aa0a6"
            groove, handle = "#444", "#ffffff"
        else:
            bg, fg, border = "#ffffff", "#1f2328", "#8c959f"
            btn_bg, btn_hover = "#f6f8fa", "#e9ecef"
            status_color = "#57606a"
            groove, handle = "#d0d7de", "#1f2328"
        sheet = f"""
        #panel {{
            background: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: {PANEL_RADIUS}px;
        }}
        QLabel {{ color: {fg}; }}
        #track_label {{ font-size: 13px; font-weight: 600; }}
        #settings_title {{ font-size: 15px; font-weight: 700; }}
        #status_label, #listeners_label, #settings_status {{
            color: {status_color}; font-size: 11px;
        }}
        #album_art {{
            background: {btn_bg};
            color: {status_color};
            border-radius: 8px;
            font-size: 12px;
        }}
        QCheckBox {{ color: {fg}; spacing: 7px; }}
        QPushButton {{
            background: {btn_bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 6px 10px;
        }}
        QPushButton:hover {{ background: {btn_hover}; }}
        QComboBox {{
            background: {btn_bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: {groove};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 12px;
            margin: -5px 0;
            background: {handle};
            border-radius: 6px;
        }}
        """
        self.setStyleSheet(sheet)

    def _on_bitrate(self, _index: int) -> None:
        self.bitrate_changed.emit(str(self._bitrate.currentData()))

    def set_track_text(self, text: str) -> None:
        self._track.setText(text)

    def set_album_art(self, data: bytes | None) -> None:
        pixmap = QPixmap()
        loaded = bool(data) and pixmap.loadFromData(data)
        self._album_art_has_image = loaded
        if loaded:
            self._album_art.setText("")
            self._album_art.setPixmap(
                pixmap.scaled(
                    self._album_art.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._album_art.clear()
            self._album_art.setText("No Album Art")
        self._album_art.setVisible(self._album_art_enabled)
        self._resize_current_page()

    def set_album_art_visible(self, visible: bool) -> None:
        self._album_art_enabled = visible
        self._album_art.setVisible(visible)
        self._resize_current_page()

    def set_listener_count(self, count: int) -> None:
        self._listeners.setText(f"Listeners: {max(0, int(count)):,}")

    def set_listener_count_visible(self, visible: bool) -> None:
        self._listeners.setVisible(visible)
        self._resize_current_page()

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("Pause" if playing else "Play")

    def set_volume(self, volume: int) -> None:
        blocked = self._volume.blockSignals(True)
        self._volume.setValue(volume)
        self._volume.blockSignals(blocked)
        self._vol_label.setText(f"{volume}%")

    def set_bitrate(self, bitrate: str) -> None:
        blocked = self._bitrate.blockSignals(True)
        idx = self._bitrate.findData(bitrate)
        if idx >= 0:
            self._bitrate.setCurrentIndex(idx)
        self._bitrate.blockSignals(blocked)

    def set_settings(self, settings: AppConfig) -> None:
        self._loading_settings = True
        try:
            self._auto_start_login.setChecked(settings.auto_start_login)
            self._auto_play.setChecked(settings.auto_play)
            self._notify_updates.setChecked(settings.notify_updates)
            self._show_album_art.setChecked(settings.show_album_art)
            self._show_listener_count.setChecked(settings.show_listener_count)
            action = settings.tray_click_action
            index = self._tray_click_action.findData(action)
            self._tray_click_action.setCurrentIndex(max(0, index))
        finally:
            self._loading_settings = False

    def _emit_settings(self, _value: object = None) -> None:
        if self._loading_settings:
            return
        self.settings_changed.emit(
            {
                "auto_start_login": self._auto_start_login.isChecked(),
                "auto_play": self._auto_play.isChecked(),
                "notify_updates": self._notify_updates.isChecked(),
                "show_album_art": self._show_album_art.isChecked(),
                "show_listener_count": self._show_listener_count.isChecked(),
                "tray_click_action": str(self._tray_click_action.currentData()),
            }
        )

    def set_settings_status(self, text: str) -> None:
        self._settings_status.setText(text)
        self._resize_current_page()

    def _resize_current_page(self) -> None:
        page = self._pages.currentWidget()
        if page is None:
            return
        if page.layout() is not None:
            page.layout().activate()
        self._pages.setFixedHeight(page.sizeHint().height())
        self._panel.layout().activate()
        self.resize(self.width(), self._panel.sizeHint().height() + 2 * SHADOW_MARGIN)
        # QStackedWidget updates the parent's minimum size on the next event
        # turn. Resize once more then so a shorter settings page can shrink
        # after an artwork-heavy playback page.
        QTimer.singleShot(0, self._finish_page_resize)

    def _finish_page_resize(self) -> None:
        self._panel.layout().activate()
        self.resize(self.width(), self._panel.sizeHint().height() + 2 * SHADOW_MARGIN)
        if self.isVisible() and self._last_anchor is not None:
            self._move_to_anchor(self._last_anchor)

    def show_settings_page(self) -> None:
        self._pages.setCurrentWidget(self._settings_page)
        self._resize_current_page()

    def show_playback_page(self) -> None:
        self._pages.setCurrentWidget(self._playback_page)
        self._resize_current_page()

    def popup_at(self, global_pos) -> None:
        self._last_anchor = global_pos
        self._resize_current_page()
        self._move_to_anchor(global_pos)
        self._arm_outside_click_guard()
        if sys.platform == "darwin":
            # A menu-bar accessory can still be inactive on its first open.
            # activateWindow() alone then lets the first content click get consumed
            # as application activation instead of delivering it to a control.
            platform_mac.activate_app()
        self.show()
        self.raise_()
        self.activateWindow()

    def _move_to_anchor(self, global_pos) -> None:
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        if screen is None:
            self.move(global_pos)
        else:
            geo = screen.availableGeometry()
            w, h = self.width(), self.height()
            # Place the visible panel edge near the tray; undo the shadow inset.
            gap = 10 - SHADOW_MARGIN
            x = min(
                max(global_pos.x() - w // 2, geo.left() - SHADOW_MARGIN),
                geo.left() + geo.width() - w + SHADOW_MARGIN,
            )
            y = global_pos.y() - h - gap
            if y < geo.top() - SHADOW_MARGIN:
                y = global_pos.y() + gap
            if y + h > geo.top() + geo.height() + SHADOW_MARGIN:
                y = geo.top() + geo.height() - h + SHADOW_MARGIN
            if y < geo.top() - SHADOW_MARGIN:
                y = geo.top() - SHADOW_MARGIN
            self.move(x, y)

    def hide_for_toggle(self) -> None:
        """Hide because the tray left-click toggle asked us to.

        Marks the hide as programmatic so the same click's activation is not
        mistaken for the tail of an outside-click auto-close.
        """
        self._programmatic_hide = True
        self.hide()

    def consume_auto_close_tail(self) -> bool:
        """True if the current tray activation is the tail of the same outside
        click that just auto-closed this popup.

        On Windows/Linux the Qt.Popup grabs the mouse, so clicking the tray
        icon while open auto-closes the popup on the press; the same click's
        release then reaches the tray and emits activated(Trigger). Without
        this guard the toggle would reopen the popup forever.
        """
        if time.monotonic() - self._auto_closed_at < AUTO_CLOSE_TAIL_MS / 1000.0:
            self._auto_closed_at = 0.0
            return True
        return False

    def _arm_outside_click_guard(self) -> None:
        if sys.platform == "darwin":
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
            self._mouse_monitor = platform_mac.monitor_mouse_down(self._outside_clicked.emit)
            return
        self._ignore_outside_until = time.monotonic() + OUTSIDE_CLICK_GUARD_MS / 1000.0
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _disarm_outside_click_guard(self) -> None:
        self._ignore_outside_until = 0.0
        platform_mac.stop_monitor(self._mouse_monitor)
        self._mouse_monitor = None
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def _child_popup_open(self) -> bool:
        """True while a nested Qt popup (e.g. QComboBox list) is open."""
        return QApplication.activePopupWidget() is not None

    def _panel_geometry_contains(self, global_pos) -> bool:
        """Hit-test the rounded panel (not the translucent shadow margin)."""
        origin = self._panel.mapToGlobal(self._panel.rect().topLeft())
        return self._panel.rect().translated(origin).contains(global_pos)

    def _on_global_mouse_down(self) -> None:
        """Ignore native monitor callbacks for clicks that landed in the panel."""
        if (
            self.isVisible()
            and not self._child_popup_open()
            and not self._panel_geometry_contains(QCursor.pos())
        ):
            self.hide()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            sys.platform == "darwin"
            and self.isVisible()
            and not self._child_popup_open()
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and not self._panel_geometry_contains(event.globalPosition().toPoint())
        ):
            self.hide()
            return False
        if (
            self.isVisible()
            and self._ignore_outside_until
            and time.monotonic() < self._ignore_outside_until
            and event.type()
            in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            )
            and isinstance(event, QMouseEvent)
            and not self._panel_geometry_contains(event.globalPosition().toPoint())
        ):
            return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        if self._programmatic_hide:
            self._programmatic_hide = False
            self._auto_closed_at = 0.0
        else:
            self._auto_closed_at = time.monotonic()
        self._disarm_outside_click_guard()
        super().hideEvent(event)
