from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class TrayPopup(QWidget):
    """Non-modal popup anchored near the tray / cursor."""

    play_pause_clicked = Signal()
    volume_changed = Signal(int)
    volume_released = Signal()
    bitrate_changed = Signal(str)
    open_site_clicked = Signal()
    quit_clicked = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setFixedWidth(300)

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

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        root.addWidget(self._track)
        root.addWidget(self._status)
        root.addLayout(vol_row)
        root.addLayout(btn_row)
        root.addLayout(foot)

        self.setStyleSheet(
            """
            TrayPopup {
                background: #1e1e1e;
                color: #f0f0f0;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QLabel { color: #f0f0f0; }
            QPushButton {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QPushButton:hover { background: #3a3a3a; }
            QComboBox {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #444;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 12px;
                margin: -5px 0;
                background: #2F6FED;
                border-radius: 6px;
            }
            """
        )

        self._volume.valueChanged.connect(lambda v: self._vol_label.setText(f"{v}%"))

        self._apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._apply_theme)

    def _apply_theme(self, _scheme: object = None) -> None:
        dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        if dark:
            bg, fg, border = "#1e1e1e", "#f0f0f0", "#3a3a3a"
            btn_bg, btn_hover = "#2d2d2d", "#3a3a3a"
            status_color = "#9aa0a6"
            groove, accent = "#444", "#2F6FED"
        else:
            bg, fg, border = "#ffffff", "#1f2328", "#d0d7de"
            btn_bg, btn_hover = "#f6f8fa", "#e9ecef"
            status_color = "#57606a"
            groove, accent = "#d0d7de", "#2F6FED"
        sheet = """
        TrayPopup {
            background: __BG__;
            color: __FG__;
            border: 1px solid __BORDER__;
            border-radius: 8px;
        }
        QLabel { color: __FG__; }
        #track_label { font-size: 13px; font-weight: 600; }
        #status_label { color: __STATUS__; font-size: 11px; }
        QPushButton {
            background: __BTN__;
            color: __FG__;
            border: 1px solid __BORDER__;
            border-radius: 4px;
            padding: 6px 10px;
        }
        QPushButton:hover { background: __BTNHOVER__; }
        QComboBox {
            background: __BTN__;
            color: __FG__;
            border: 1px solid __BORDER__;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: __GROOVE__;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            width: 12px;
            margin: -5px 0;
            background: __ACCENT__;
            border-radius: 6px;
        }
        """
        for key, val in {
            "__BG__": bg, "__FG__": fg, "__BORDER__": border,
            "__BTN__": btn_bg, "__BTNHOVER__": btn_hover,
            "__STATUS__": status_color, "__GROOVE__": groove, "__ACCENT__": accent,
        }.items():
            sheet = sheet.replace(key, val)
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
            self.show()
            self.raise_()
            self.activateWindow()
            return
        geo = screen.availableGeometry()
        w, h = self.sizeHint().width(), self.sizeHint().height()
        x = min(max(global_pos.x() - w // 2, geo.left() + 8), geo.right() - w - 8)
        y = global_pos.y() - h - 12
        if y < geo.top() + 8:
            y = global_pos.y() + 12
        if y + h > geo.bottom() - 8:
            y = geo.bottom() - h - 8
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
