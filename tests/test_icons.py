from __future__ import annotations

from PySide6.QtGui import QColor

from coderadio_tray.ui import icons
from coderadio_tray.ui.icons import (
    TRAY_ICON_SIZES,
    _render_app_pixmap,
    _render_tray_pixmap,
    make_app_icon,
    make_tray_icon,
)


def _force_platform_ink(monkeypatch, *, is_mask):
    """Force a deterministic ink + mask flag regardless of host platform."""
    from PySide6.QtGui import QColor

    ink = QColor(0, 0, 0) if is_mask else QColor(255, 255, 255)
    monkeypatch.setattr(icons, "_platform_ink", lambda: (ink, is_mask))


def test_tray_icon_is_mask_on_template_platform(monkeypatch, qapp):
    _force_platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False)
    assert icon.isMask() is True


def test_tray_icon_not_mask_on_colorink_platform(monkeypatch, qapp):
    _force_platform_ink(monkeypatch, is_mask=False)
    icon = make_tray_icon(playing=True)
    assert icon.isMask() is False


def test_tray_icon_has_standard_sizes(monkeypatch, qapp):
    _force_platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False, error=False)
    sizes = icon.availableSizes()
    assert len(sizes) > 0
    assert {size.height() for size in sizes} == set(TRAY_ICON_SIZES)
    if icons.sys.platform == "win32":
        assert all(size.width() == size.height() for size in sizes)
    else:
        assert all(size.width() > size.height() for size in sizes)


def test_windows_tray_icon_is_square_and_taller_fill(monkeypatch, qapp):
    monkeypatch.setattr(icons.sys, "platform", "win32")
    pixmap = _render_tray_pixmap(32, playing=True, error=False, ink=QColor("#ffffff"))
    assert pixmap.width() == 32
    assert pixmap.height() == 32
    image = pixmap.toImage()
    top_band = sum(
        image.pixelColor(x, y).alpha() for y in range(max(1, 32 // 10)) for x in range(32)
    )
    assert top_band > 0
    # Paused must keep full brackets (compression, not side-crop).
    paused = _render_tray_pixmap(64, playing=False, error=False, ink=QColor("#ffffff"))
    pimg = paused.toImage()
    left_ink = sum(
        1
        for y in range(pimg.height())
        for x in range(pimg.width() // 5)
        if pimg.pixelColor(x, y).alpha() > 10
    )
    assert left_ink > 50


def test_non_windows_tray_icon_stays_rectangular(monkeypatch, qapp):
    monkeypatch.setattr(icons.sys, "platform", "darwin")
    pixmap = _render_tray_pixmap(32, playing=True, error=False, ink=QColor("#ffffff"))
    assert pixmap.width() > pixmap.height()


def test_tray_icon_error_state_renders(monkeypatch, qapp):
    _force_platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False, error=True)
    # Should not raise and should produce a non-null pixmap at a usable size.
    pm = icon.pixmap(32)
    assert not pm.isNull()


def _center_alpha_count(pixmap) -> int:
    image = pixmap.toImage()
    left = image.width() // 4
    right = image.width() * 3 // 4
    return sum(
        image.pixelColor(x, y).alpha() for y in range(image.height()) for x in range(left, right)
    )


def test_playing_icon_keeps_center_campfire(qapp):
    pixmap = _render_tray_pixmap(128, playing=True, error=False, ink=QColor("#ffffff"))
    assert _center_alpha_count(pixmap) > 0


def test_paused_icon_removes_center_and_keeps_brackets(qapp):
    pixmap = _render_tray_pixmap(128, playing=False, error=False, ink=QColor("#ffffff"))
    image = pixmap.toImage()
    assert _center_alpha_count(pixmap) == 0
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(image.height())
        for x in range(image.width() // 4)
    )
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(image.height())
        for x in range(image.width() * 3 // 4, image.width())
    )


def test_app_icon_source_logo_renders(qapp):
    icon = make_app_icon()
    pm = icon.pixmap(256)
    assert not pm.isNull()
    assert len(icon.availableSizes()) >= 4


def test_app_icon_has_navy_tile_and_white_mark(qapp):
    image = _render_app_pixmap(256).toImage()
    # Outside the rounded tile: transparent corner.
    assert image.pixelColor(0, 0).alpha() < 10

    # Sample the tile face away from the logo and the top gloss hotspot.
    face = image.pixelColor(48, 200)
    assert face.alpha() > 200
    assert face.blue() > face.red()
    assert face.lightness() < 48

    # White FCC mark is present (brackets / campfire).
    assert any(
        image.pixelColor(x, y).alpha() > 200 and image.pixelColor(x, y).lightness() > 223
        for y in range(image.height())
        for x in range(image.width())
    )


def test_macos_uses_black_template_ink(monkeypatch, qapp):
    monkeypatch.setattr(icons.sys, "platform", "darwin")
    ink, is_mask = icons._platform_ink()
    assert ink == QColor("#000000")
    assert is_mask is True


def test_windows_light_taskbar_uses_dark_ink(monkeypatch, qapp):
    monkeypatch.setattr(icons.sys, "platform", "win32")
    monkeypatch.setattr(icons, "_win_taskbar_is_light", lambda: True)
    ink, is_mask = icons._platform_ink()
    assert ink == QColor("#1a1a1a")
    assert is_mask is False


def test_windows_dark_taskbar_uses_light_ink(monkeypatch, qapp):
    monkeypatch.setattr(icons.sys, "platform", "win32")
    monkeypatch.setattr(icons, "_win_taskbar_is_light", lambda: False)
    ink, is_mask = icons._platform_ink()
    assert ink == QColor("#f5f5f5")
    assert is_mask is False
