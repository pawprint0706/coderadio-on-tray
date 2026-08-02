from __future__ import annotations

import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import QBuffer, QEvent, QIODevice, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent

from coderadio_tray.config import AppConfig
from coderadio_tray.ui.popup import TrayPopup


def _png_bytes() -> bytes:
    image = QImage(24, 24, QImage.Format.Format_ARGB32)
    image.fill(QColor("#336699"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_popup_light_theme_sheet(qapp):
    popup = TrayPopup()
    popup._apply_theme(Qt.ColorScheme.Light)
    sheet = popup.styleSheet()
    assert "#ffffff" in sheet  # light background
    assert "#1f2328" in sheet  # dark text
    assert "#1e1e1e" not in sheet  # no dark bg
    assert "border-radius: 12px" in sheet
    assert "border: 1px solid" in sheet


def test_popup_dark_theme_sheet(qapp):
    popup = TrayPopup()
    popup._apply_theme(Qt.ColorScheme.Dark)
    sheet = popup.styleSheet()
    assert "#1e1e1e" in sheet  # dark background
    assert "#f0f0f0" in sheet  # light text
    assert "border-radius: 12px" in sheet
    assert "#5a5a5a" in sheet  # stronger outer border


def test_popup_uses_rounded_panel_shell(qapp):
    popup = TrayPopup()
    assert popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert popup._panel.objectName() == "panel"
    assert popup._panel.graphicsEffect() is not None


def test_popup_set_playing_toggles_button_label(qapp):
    popup = TrayPopup()
    popup.set_playing(True)
    assert popup._play_btn.text() == "Pause"
    popup.set_playing(False)
    assert popup._play_btn.text() == "Play"


def test_popup_volume_label_updates(qapp):
    popup = TrayPopup()
    popup.set_volume(42)
    assert popup._vol_label.text() == "42%"


def test_popup_displays_album_art_above_track(qapp):
    popup = TrayPopup()
    popup.set_album_art_visible(True)
    popup.set_album_art(_png_bytes())

    assert popup._album_art.pixmap() is not None
    assert not popup._album_art.isHidden()
    assert popup._playback_page.layout().indexOf(
        popup._album_art
    ) < popup._playback_page.layout().indexOf(popup._track)

    popup.set_album_art_visible(False)
    assert popup._album_art.isHidden()


@pytest.mark.parametrize("data", [None, b"not-an-image"])
def test_popup_shows_placeholder_when_album_art_cannot_be_displayed(qapp, data):
    popup = TrayPopup()
    popup.set_album_art_visible(True)

    popup.set_album_art(data)

    assert not popup._album_art.isHidden()
    assert popup._album_art.pixmap().isNull()
    assert popup._album_art.text() == "No Album Art"


def test_popup_listener_count_and_visibility(qapp):
    popup = TrayPopup()
    popup.set_listener_count(1234)
    popup.set_listener_count_visible(True)

    assert popup._listeners.text() == "Listeners: 1,234"
    assert not popup._listeners.isHidden()
    popup.set_listener_count_visible(False)
    assert popup._listeners.isHidden()


def test_popup_switches_between_playback_and_settings_pages(qapp):
    popup = TrayPopup()

    popup.show_settings_page()
    assert popup._pages.currentWidget() is popup._settings_page
    popup.show_playback_page()
    assert popup._pages.currentWidget() is popup._playback_page


def test_popup_settings_use_equal_side_margins_and_put_updates_below_tray_action(qapp):
    popup = TrayPopup()
    layout = popup._settings_page.layout()
    margins = layout.contentsMargins()

    assert margins.left() == margins.right()
    assert layout.indexOf(popup._notify_updates) == layout.indexOf(popup._tray_click_action) + 1


def test_popup_settings_round_trip_without_initial_signal(qapp):
    popup = TrayPopup()
    emitted: list[dict] = []
    popup.settings_changed.connect(emitted.append)
    config = AppConfig(
        auto_start_login=True,
        auto_play=False,
        notify_updates=False,
        show_album_art=False,
        show_listener_count=False,
        tray_click_action="popup",
    )

    popup.set_settings(config)

    assert emitted == []
    assert popup._auto_start_login.isChecked()
    assert not popup._auto_play.isChecked()
    assert popup._tray_click_action.currentData() == "popup"

    popup._show_album_art.setChecked(True)
    assert emitted[-1]["show_album_art"] is True
    assert emitted[-1]["tray_click_action"] == "popup"


def test_popup_escape_hides(qapp):
    popup = TrayPopup()
    popup.popup_at(QPoint(200, 200))
    assert popup.isVisible()
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    popup.keyPressEvent(event)
    assert not popup.isVisible()


def test_popup_window_type_matches_platform(qapp):
    popup = TrayPopup()
    flags = int(popup.windowFlags())
    if sys.platform == "darwin":
        # Qt.Tool includes the Popup bit in its enum value; assert Tool specifically.
        assert flags & int(Qt.WindowType.Tool) == int(Qt.WindowType.Tool)
    else:
        assert flags & int(Qt.WindowType.Popup) == int(Qt.WindowType.Popup)
        assert flags & int(Qt.WindowType.Tool) != int(Qt.WindowType.Tool)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific activation")
@patch("coderadio_tray.ui.popup.platform_mac.activate_app")
def test_popup_at_activates_the_macos_accessory_app(activate, qapp):
    popup = TrayPopup()
    popup.popup_at(QPoint(200, 200))
    try:
        activate.assert_called_once_with()
    finally:
        popup.hide()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific mouse monitor")
def test_global_monitor_does_not_close_for_a_click_inside_the_panel(qapp):
    popup = TrayPopup()
    popup.popup_at(QPoint(200, 200))
    try:
        with patch(
            "coderadio_tray.ui.popup.QCursor.pos",
            return_value=popup._panel.mapToGlobal(popup._panel.rect().center()),
        ):
            popup._outside_clicked.emit()
        assert popup.isVisible()
    finally:
        popup.hide()
