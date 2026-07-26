from __future__ import annotations

from coderadio_tray.ui.icons import make_app_icon, make_tray_icon


def _platform_ink(monkeypatch, *, is_mask):
    """Force a deterministic ink + mask flag regardless of host platform."""
    from PySide6.QtGui import QColor

    from coderadio_tray.ui import icons

    ink = QColor(0, 0, 0) if is_mask else QColor(255, 255, 255)
    monkeypatch.setattr(icons, "_platform_ink", lambda: (ink, is_mask))


def test_tray_icon_is_mask_on_template_platform(monkeypatch, qapp):
    _platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False)
    assert icon.isMask() is True


def test_tray_icon_not_mask_on_colorink_platform(monkeypatch, qapp):
    _platform_ink(monkeypatch, is_mask=False)
    icon = make_tray_icon(playing=True)
    assert icon.isMask() is False


def test_tray_icon_has_standard_sizes(monkeypatch, qapp):
    _platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False, error=False)
    sizes = icon.availableSizes()
    assert len(sizes) > 0


def test_tray_icon_error_state_renders(monkeypatch, qapp):
    _platform_ink(monkeypatch, is_mask=True)
    icon = make_tray_icon(playing=False, error=True)
    # Should not raise and should produce a non-null pixmap at a usable size.
    pm = icon.pixmap(32)
    assert not pm.isNull()


def test_app_icon_campfire_renders(qapp):
    icon = make_app_icon()
    pm = icon.pixmap(256)
    assert not pm.isNull()
    assert len(icon.availableSizes()) >= 4
