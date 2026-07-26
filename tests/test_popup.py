from __future__ import annotations

from PySide6.QtCore import Qt

from coderadio_tray.ui.popup import TrayPopup


def test_popup_light_theme_sheet(qapp):
    popup = TrayPopup()
    popup._apply_theme(Qt.ColorScheme.Light)
    sheet = popup.styleSheet()
    assert "#ffffff" in sheet  # light background
    assert "#1f2328" in sheet  # dark text
    assert "#1e1e1e" not in sheet  # no dark bg


def test_popup_dark_theme_sheet(qapp):
    popup = TrayPopup()
    popup._apply_theme(Qt.ColorScheme.Dark)
    sheet = popup.styleSheet()
    assert "#1e1e1e" in sheet  # dark background
    assert "#f0f0f0" in sheet  # light text


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
