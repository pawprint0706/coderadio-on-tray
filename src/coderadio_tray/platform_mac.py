"""macOS-only integration: menu-bar accessory, activation, outside-click monitor.

Every function is a no-op on other platforms or when PyObjC is unavailable.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

logger = logging.getLogger(__name__)

_ACCESSORY_POLICY = 1  # NSApplicationActivationPolicyAccessory


def _shared_app():
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSApplication

        return NSApplication.sharedApplication()
    except Exception:
        logger.debug("AppKit is unavailable", exc_info=True)
        return None


def hide_dock_icon() -> None:
    """Run as a menu-bar accessory: no Dock icon, no app menu.

    Accessory rather than Prohibited, so modal dialogs still work.
    Must run on the main thread (after QApplication exists is fine).
    """
    app = _shared_app()
    if app is None:
        return
    try:
        app.setActivationPolicy_(_ACCESSORY_POLICY)
    except Exception:
        logger.debug("Could not set the accessory activation policy", exc_info=True)


def activate_app() -> None:
    """Bring our windows forward so the popup can take the first content click."""
    app = _shared_app()
    if app is None:
        return
    try:
        app.activateIgnoringOtherApps_(True)
    except Exception:
        logger.debug("Could not activate the application", exc_info=True)


def monitor_mouse_down(callback: Callable[[], None]) -> object | None:
    """Call ``callback`` for clicks delivered to another macOS application."""
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import (
            NSEvent,
            NSEventMaskLeftMouseDown,
            NSEventMaskOtherMouseDown,
            NSEventMaskRightMouseDown,
        )

        mask = NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown | NSEventMaskOtherMouseDown
        return NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, lambda _event: callback()
        )
    except Exception:
        logger.debug("Could not install the global mouse monitor", exc_info=True)
        return None


def stop_monitor(monitor: object | None) -> None:
    if monitor is None or sys.platform != "darwin":
        return
    try:
        from AppKit import NSEvent

        NSEvent.removeMonitor_(monitor)
    except Exception:
        logger.debug("Could not remove the global mouse monitor", exc_info=True)
