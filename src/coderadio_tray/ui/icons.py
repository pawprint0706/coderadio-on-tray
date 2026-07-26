from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPixmap,
    QPolygonF,
)


def _win_taskbar_is_light() -> bool | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            winreg.KEY_READ,
        ) as key:
            # The tray icon sits on the taskbar, whose color follows
            # SystemUsesLightTheme (the "Windows mode"). AppsUseLightTheme is
            # the independent app-window mode and would pick the wrong ink
            # under the default "apps light, taskbar dark" combo.
            value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
            return value == 1
    except OSError:
        return None


def _linux_is_light() -> bool:
    scheme = QGuiApplication.styleHints().colorScheme()
    return scheme == Qt.ColorScheme.Light


def _platform_ink() -> tuple[QColor, bool]:
    if sys.platform == "darwin":
        return QColor(0, 0, 0), True
    if sys.platform == "win32":
        light = _win_taskbar_is_light()
    else:
        light = _linux_is_light()
    ink = QColor("#1a1a1a") if light else QColor("#f5f5f5")
    return ink, False


def _render_pixmap(size: int, *, playing: bool, error: bool, ink: QColor) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, size // 16)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(ink)
    painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)

    painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    painter.setBrush(QColor(0, 0, 0, 255))
    if error:
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(8, int(size * 0.62)))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "!")
    elif playing:
        bar_w = max(2, size // 8)
        gap = max(1, size // 16)
        total = bar_w * 2 + gap
        x0 = (size - total) // 2
        y0 = size // 4
        h = size // 2
        painter.drawRoundedRect(x0, y0, bar_w, h, 1, 1)
        painter.drawRoundedRect(x0 + bar_w + gap, y0, bar_w, h, 1, 1)
    else:
        tri = QPolygonF(
            [
                QPointF(size * 0.38, size * 0.28),
                QPointF(size * 0.38, size * 0.72),
                QPointF(size * 0.72, size * 0.5),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(tri)

    painter.end()
    return pixmap


def make_tray_icon(*, playing: bool = False, error: bool = False) -> QIcon:
    ink, is_mask = _platform_ink()
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_render_pixmap(size, playing=playing, error=error, ink=ink))
    if is_mask:
        icon.setIsMask(True)
    return icon