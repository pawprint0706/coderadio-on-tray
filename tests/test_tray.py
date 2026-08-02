from __future__ import annotations

from PySide6.QtGui import QIcon

import coderadio_tray.ui.tray as tray_module
from coderadio_tray.ui.tray import TrayController


class _PopupStub:
    def __init__(self) -> None:
        self.playing = False

    def set_playing(self, playing: bool) -> None:
        self.playing = playing


def test_error_icon_blinks_every_second_and_stops_when_cleared(monkeypatch, qapp):
    rendered: list[tuple[bool, bool]] = []

    def fake_icon(*, playing=False, error=False, error_visible=True):
        rendered.append((error, error_visible))
        return QIcon()

    monkeypatch.setattr(tray_module, "make_tray_icon", fake_icon)
    controller = TrayController(_PopupStub())

    controller.set_playing(False, error=True)
    assert controller._error_blink_timer.interval() == 1000
    assert controller._error_blink_timer.isActive()
    assert rendered[-1] == (True, True)

    controller._toggle_error_blink()
    assert rendered[-1] == (True, False)
    controller._toggle_error_blink()
    assert rendered[-1] == (True, True)

    controller.set_playing(False, error=False)
    assert not controller._error_blink_timer.isActive()
    assert rendered[-1] == (False, False)
