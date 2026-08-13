from __future__ import annotations

from PySide6.QtGui import QIcon

import coderadio_tray.ui.tray as tray_module
from coderadio_tray.ui.tray import TrayController


class _PopupStub:
    def __init__(self) -> None:
        self.playing = False
        self.popup_positions = []
        self.visible = False
        self.hidden_count = 0
        self.consume_tails = 0

    def set_playing(self, playing: bool) -> None:
        self.playing = playing

    def isVisible(self) -> bool:  # noqa: N802
        return self.visible

    def hide(self) -> None:
        self.visible = False
        self.hidden_count += 1

    def hide_for_toggle(self) -> None:
        self.hide()

    def consume_auto_close_tail(self) -> bool:
        self.consume_tails += 1
        return getattr(self, "auto_close_tail", False)

    def popup_at(self, position) -> None:
        self.visible = True
        self.popup_positions.append(position)


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


def test_left_click_can_open_popup(monkeypatch, qapp):
    monkeypatch.setattr(tray_module, "make_tray_icon", lambda **_kwargs: QIcon())
    popup = _PopupStub()
    controller = TrayController(popup)
    toggles: list[bool] = []
    controller.on_left_click(lambda: toggles.append(True))
    controller.set_left_click_action("popup")

    controller._on_activated(controller.tray.ActivationReason.Trigger)

    assert len(popup.popup_positions) == 1
    assert toggles == []


def test_left_click_toggles_popup_open_and_closed(monkeypatch, qapp):
    monkeypatch.setattr(tray_module, "make_tray_icon", lambda **_kwargs: QIcon())
    popup = _PopupStub()
    controller = TrayController(popup)
    controller.set_left_click_action("popup")

    controller._on_activated(controller.tray.ActivationReason.Trigger)
    assert len(popup.popup_positions) == 1
    assert popup.isVisible()

    controller._on_activated(controller.tray.ActivationReason.Trigger)
    assert len(popup.popup_positions) == 1
    assert not popup.isVisible()
    assert popup.hidden_count == 1
    assert popup.consume_tails == 1


def test_left_click_does_not_reopen_popup_auto_closed_by_same_click(monkeypatch, qapp):
    """Regression: on Windows/Linux a Qt.Popup auto-closes on the tray click's
    press, then the same click's release emits activated(Trigger). The tail
    activation must not reopen the popup or the toggle never closes."""
    monkeypatch.setattr(tray_module, "make_tray_icon", lambda **_kwargs: QIcon())
    popup = _PopupStub()
    controller = TrayController(popup)
    controller.set_left_click_action("popup")

    controller._on_activated(controller.tray.ActivationReason.Trigger)
    assert popup.isVisible()

    popup.auto_close_tail = True
    popup.visible = False  # the same click's press auto-closed the Qt.Popup
    controller._on_activated(controller.tray.ActivationReason.Trigger)

    assert len(popup.popup_positions) == 1
    assert not popup.isVisible()
    assert popup.hidden_count == 0
    assert popup.consume_tails == 2


def test_notification_click_runs_handler(monkeypatch, qapp):
    monkeypatch.setattr(tray_module, "make_tray_icon", lambda **_kwargs: QIcon())
    controller = TrayController(_PopupStub())
    clicks: list[bool] = []
    controller.show_message("Update", "Available", on_click=lambda: clicks.append(True))

    controller._on_message_clicked()
    controller._on_message_clicked()

    assert clicks == [True]
