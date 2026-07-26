"""Tray and application icons based on the supplied freeCodeCamp mark."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPainter, QPixmap

TRAY_ICON_SIZES = (16, 18, 20, 22, 24, 32, 44, 48, 64)


def resources_icons_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "icons"


@lru_cache(maxsize=1)
def _source_logo_image() -> QImage:
    path = resources_icons_dir() / "source" / "fcc_primary_small.png"
    image = QImage(str(path))
    if image.isNull():
        raise RuntimeError(f"FCC icon source is missing or invalid: {path}")
    return image


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


def _logo_image(*, brackets_only: bool, ink: QColor | None) -> QImage:
    image = _source_logo_image().copy()

    if brackets_only:
        # In the 712px source, the left bracket ends at x=141 and the right
        # bracket starts at x=570. Clearing only the middle preserves the two
        # original bracket paths pixel-for-pixel while removing the campfire.
        left = round(image.width() * 142 / 712)
        right = round(image.width() * 570 / 712)
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(left, 0, right - left, image.height(), Qt.GlobalColor.transparent)
        painter.end()

    if ink is not None:
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(image.rect(), ink)
        painter.end()

    return image


def _render_logo_pixmap(
    size: int,
    *,
    brackets_only: bool = False,
    ink: QColor | None = None,
    rectangular: bool = False,
) -> QPixmap:
    source = QPixmap.fromImage(_logo_image(brackets_only=brackets_only, ink=ink))
    target_height = max(1, round(size * 0.98))
    scaled = source.scaledToHeight(
        target_height,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas_width = scaled.width() if rectangular else size
    if not rectangular and scaled.width() > size:
        scaled = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    canvas = QPixmap(canvas_width, size)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawPixmap(
        (canvas.width() - scaled.width()) // 2,
        (canvas.height() - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas


def _render_tray_pixmap(size: int, *, playing: bool, error: bool, ink: QColor) -> QPixmap:
    if error:
        pixmap = _render_logo_pixmap(size, ink=QColor("#e53935"), rectangular=True)
        painter = QPainter(pixmap)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(8, int(size * 0.42)))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "!")
        painter.end()
        return pixmap

    # Playing shows the supplied logo unchanged. Paused/stopped removes only
    # the center campfire, leaving the original left/right bracket silhouettes.
    return _render_logo_pixmap(size, brackets_only=not playing, ink=ink, rectangular=True)


def _render_app_pixmap(size: int) -> QPixmap:
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)

    source = QPixmap.fromImage(_logo_image(brackets_only=False, ink=None))
    max_extent = max(1, round(size * 0.90))
    logo = source.scaled(
        max_extent,
        max_extent,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    black = QPixmap.fromImage(_logo_image(brackets_only=False, ink=QColor("#000000")))
    black = black.scaled(
        logo.size(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    x = (size - logo.width()) // 2
    y = (size - logo.height()) // 2
    stroke = max(1, round(size * 0.018))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for dx, dy in (
        (-stroke, -stroke),
        (0, -stroke),
        (stroke, -stroke),
        (-stroke, 0),
        (stroke, 0),
        (-stroke, stroke),
        (0, stroke),
        (stroke, stroke),
    ):
        painter.drawPixmap(x + dx, y + dy, black)
    painter.drawPixmap(x, y, logo)
    painter.end()
    return canvas


def make_tray_icon(*, playing: bool = False, error: bool = False) -> QIcon:
    ink, is_mask = _platform_ink()
    icon = QIcon()
    for size in TRAY_ICON_SIZES:
        icon.addPixmap(_render_tray_pixmap(size, playing=playing, error=error, ink=ink))
    if is_mask and not error:
        icon.setIsMask(True)
    return icon


def make_app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon.addPixmap(_render_app_pixmap(size))
    return icon
