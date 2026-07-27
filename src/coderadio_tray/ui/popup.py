from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from coderadio_tray import platform_mac

# Non-macOS Qt.Popup windows need to swallow the tray interaction briefly.
OUTSIDE_CLICK_GUARD_MS = 300
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

        self._track = QLabel("Code Radio")
        self._track.setObjectName("track_label")
        self._track.setWordWrap(True)

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

        site_btn = QPushButton("Open site")
        site_btn.clicked.connect(self.open_site_clicked.emit)
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.quit_clicked.emit)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Vol"))
        vol_row.addWidget(self._volume, stretch=1)
        vol_row.addWidget(self._vol_label)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._bitrate)

        foot = QHBoxLayout()
        foot.addWidget(site_btn)
        foot.addStretch(1)
        foot.addWidget(quit_btn)

        root = QVBoxLayout(self._panel)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(self._track)
        root.addWidget(self._status)
        root.addLayout(vol_row)
        root.addLayout(btn_row)
        root.addLayout(foot)

        self._volume.valueChanged.connect(lambda v: self._vol_label.setText(f"{v}%"))

        self._apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._apply_theme)

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
        #status_label {{ color: {status_color}; font-size: 11px; }}
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

    def popup_at(self, global_pos) -> None:
        self.adjustSize()
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
        self._arm_outside_click_guard()
        if sys.platform == "darwin":
            # A menu-bar accessory can still be inactive on its first open.
            # activateWindow() alone then lets the first content click get consumed
            # as application activation instead of delivering it to a control.
            platform_mac.activate_app()
        self.show()
        self.raise_()
        self.activateWindow()

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
        self._disarm_outside_click_guard()
        super().hideEvent(event)
