"""Tray and application icons (campfire motif).

Campfire silhouette is an original drawing inspired by the freeCodeCamp
campfire motif (community / Code Radio association). This is an unofficial
client — not the official freeCodeCamp trademark asset.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)

# Brand-ish palette (inspired by freeCodeCamp warmth / dark navy)
APP_BG = QColor("#0a0a23")
APP_FLAME = QColor("#ffffff")


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


def _campfire_path(size: float) -> QPainterPath:
    """Normalized campfire glyph scaled to ``size`` (square)."""
    s = size
    path = QPainterPath()

    # Left flame
    path.moveTo(0.28 * s, 0.72 * s)
    path.cubicTo(0.18 * s, 0.55 * s, 0.22 * s, 0.38 * s, 0.32 * s, 0.28 * s)
    path.cubicTo(0.30 * s, 0.42 * s, 0.34 * s, 0.55 * s, 0.38 * s, 0.66 * s)
    path.closeSubpath()

    # Center flame (tallest)
    path.moveTo(0.42 * s, 0.78 * s)
    path.cubicTo(0.36 * s, 0.55 * s, 0.38 * s, 0.32 * s, 0.50 * s, 0.14 * s)
    path.cubicTo(0.62 * s, 0.32 * s, 0.64 * s, 0.55 * s, 0.58 * s, 0.78 * s)
    path.closeSubpath()

    # Right flame
    path.moveTo(0.62 * s, 0.66 * s)
    path.cubicTo(0.66 * s, 0.55 * s, 0.70 * s, 0.42 * s, 0.68 * s, 0.28 * s)
    path.cubicTo(0.78 * s, 0.38 * s, 0.82 * s, 0.55 * s, 0.72 * s, 0.72 * s)
    path.closeSubpath()

    # Logs (two short bars)
    logs = QPainterPath()
    logs.addRoundedRect(QRectF(0.30 * s, 0.78 * s, 0.40 * s, 0.07 * s), 0.02 * s, 0.02 * s)
    logs.addRoundedRect(QRectF(0.34 * s, 0.86 * s, 0.32 * s, 0.06 * s), 0.02 * s, 0.02 * s)
    path.addPath(logs)
    return path


def _draw_campfire(painter: QPainter, size: int, color: QColor) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(_campfire_path(float(size)))


def _render_tray_pixmap(size: int, *, playing: bool, error: bool, ink: QColor) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    flame = QColor("#e53935") if error else ink
    _draw_campfire(painter, size, flame)

    if error:
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(8, int(size * 0.45)))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "!")
    elif playing:
        # Small pause mark punched in the lower center (DestinationOut)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        painter.setBrush(QColor(0, 0, 0, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        bar_w = max(2, size // 10)
        gap = max(1, size // 14)
        total = bar_w * 2 + gap
        x0 = (size - total) // 2
        y0 = int(size * 0.42)
        h = max(4, int(size * 0.28))
        painter.drawRoundedRect(x0, y0, bar_w, h, 1, 1)
        painter.drawRoundedRect(x0 + bar_w + gap, y0, bar_w, h, 1, 1)

    painter.end()
    return pixmap


def _render_app_pixmap(size: int) -> QPixmap:
    """Full-color app / installer icon (navy disc + white campfire)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, size // 32)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(APP_BG)
    painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)

    # Slight inset so flames don't touch the circle edge
    inset = int(size * 0.08)
    painter.translate(inset, inset)
    _draw_campfire(painter, size - inset * 2, APP_FLAME)

    painter.end()
    return pixmap


def make_tray_icon(*, playing: bool = False, error: bool = False) -> QIcon:
    ink, is_mask = _platform_ink()
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_render_tray_pixmap(size, playing=playing, error=error, ink=ink))
    if is_mask:
        icon.setIsMask(True)
    return icon


def make_app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon.addPixmap(_render_app_pixmap(size))
    return icon


def resources_icons_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "icons"
