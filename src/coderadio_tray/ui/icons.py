"""Tray and application icons based on the supplied freeCodeCamp mark.

Tray icons stay monochrome/template for the menu bar. The app icon is a
freeCodeCamp-navy (#0a0a23) high-gloss rounded tile with the white brackets
+ campfire mark (no outline stroke).
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)

# freeCodeCamp navy — app-icon tile base (high-gloss rounded square).
_APP_TILE_BASE = QColor("#0a0a23")
# macOS continuous-corner feel for a full-bleed app tile (matches llm-usage-meter).
_APP_CORNER_RATIO = 0.2237
_APP_LOGO_FILL = 0.70

TRAY_ICON_SIZES = (16, 18, 20, 22, 24, 32, 44, 48, 64)

# macOS/Linux keep a wide rectangular glyph (menu-bar friendly). Windows
# notification area is square, so a wide pixmap is letterboxed and looks small.
# On Windows we draw into a square and scale with mild horizontal compression
# (no side crop) so the paused brackets-only mark stays intact.
_WIN_TRAY_HEIGHT_FILL = 0.92
_DEFAULT_TRAY_HEIGHT_FILL = 0.98


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


def _tray_render_params() -> tuple[bool, float]:
    """Return ``(square_canvas, height_fill)`` for the current platform."""
    if sys.platform == "win32":
        return True, _WIN_TRAY_HEIGHT_FILL
    return False, _DEFAULT_TRAY_HEIGHT_FILL


def _render_logo_pixmap(
    size: int,
    *,
    brackets_only: bool = False,
    ink: QColor | None = None,
    rectangular: bool = False,
    square: bool = False,
    height_fill: float = _DEFAULT_TRAY_HEIGHT_FILL,
) -> QPixmap:
    source = QPixmap.fromImage(_logo_image(brackets_only=brackets_only, ink=ink))
    target_height = max(1, round(size * height_fill))

    if square:
        # Square slot: fill most of the height and the full width. The FCC mark
        # is wider than tall, so this applies mild horizontal compression instead
        # of cropping — needed so paused (brackets-only) stays recognizable.
        scaled = source.scaled(
            size,
            target_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, (size - scaled.height()) // 2, scaled)
        painter.end()
        return canvas

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
        canvas_width = size

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
    square, height_fill = _tray_render_params()
    if error:
        pixmap = _render_logo_pixmap(
            size,
            ink=QColor("#e53935"),
            rectangular=not square,
            square=square,
            height_fill=height_fill,
        )
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
    return _render_logo_pixmap(
        size,
        brackets_only=not playing,
        ink=ink,
        rectangular=not square,
        square=square,
        height_fill=height_fill,
    )


def _paint_app_tile(painter: QPainter, tile_rect: QRectF, radius: float) -> None:
    """High-gloss rounded square in freeCodeCamp navy (#0a0a23)."""
    shape = QPainterPath()
    shape.addRoundedRect(tile_rect, radius, radius)
    painter.setClipPath(shape)

    base = QLinearGradient(tile_rect.topLeft(), tile_rect.bottomLeft())
    base.setColorAt(0.0, QColor("#1a1a3a"))
    base.setColorAt(0.35, _APP_TILE_BASE)
    base.setColorAt(1.0, QColor("#050512"))
    painter.fillPath(shape, base)

    sheen = QLinearGradient(
        tile_rect.topLeft(), QPointF(tile_rect.center().x(), tile_rect.bottom())
    )
    sheen.setColorAt(0.0, QColor(255, 255, 255, 58))
    sheen.setColorAt(0.28, QColor(255, 255, 255, 18))
    sheen.setColorAt(0.55, QColor(255, 255, 255, 0))
    sheen.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.fillPath(shape, sheen)

    gloss = QRadialGradient(
        QPointF(tile_rect.center().x(), tile_rect.top() + tile_rect.height() * 0.18),
        tile_rect.width() * 0.55,
    )
    gloss.setColorAt(0.0, QColor(255, 255, 255, 72))
    gloss.setColorAt(0.35, QColor(255, 255, 255, 22))
    gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(shape, gloss)

    shade = QLinearGradient(
        QPointF(tile_rect.center().x(), tile_rect.center().y()), tile_rect.bottomLeft()
    )
    shade.setColorAt(0.0, QColor(0, 0, 0, 0))
    shade.setColorAt(1.0, QColor(0, 0, 0, 90))
    painter.fillPath(shape, shade)

    painter.setClipping(False)

    painter.setPen(Qt.PenStyle.NoPen)
    rim = QPainterPath(shape)
    inner = QPainterPath()
    rim_inset = max(1.5, tile_rect.width() * 0.012)
    inner.addRoundedRect(
        tile_rect.adjusted(rim_inset, rim_inset, -rim_inset, -rim_inset),
        radius * 0.92,
        radius * 0.92,
    )
    rim = rim.subtracted(inner)
    rim_grad = QLinearGradient(tile_rect.topLeft(), tile_rect.bottomRight())
    rim_grad.setColorAt(0.0, QColor(255, 255, 255, 70))
    rim_grad.setColorAt(0.45, QColor(255, 255, 255, 18))
    rim_grad.setColorAt(1.0, QColor(255, 255, 255, 8))
    painter.fillPath(rim, rim_grad)


def _render_app_pixmap(size: int) -> QPixmap:
    """Navy high-gloss tile with the white FCC brackets + campfire mark."""
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Leave a 1px optical margin so downscales keep a clean alpha edge.
    inset = max(1.0, size * 0.02)
    tile = size - 2 * inset
    radius = tile * _APP_CORNER_RATIO
    tile_rect = QRectF(inset, inset, tile, tile)
    _paint_app_tile(painter, tile_rect, radius)

    logo = QPixmap.fromImage(_logo_image(brackets_only=False, ink=QColor("#ffffff")))
    max_extent = max(1, round(tile * _APP_LOGO_FILL))
    logo = logo.scaled(
        max_extent,
        max_extent,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = round((size - logo.width()) / 2)
    y = round((size - logo.height()) / 2)
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
