from __future__ import annotations

import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent

from coderadio_tray.ui.popup import TrayPopup


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
