from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Shared QApplication for widget-level unit tests.

    On headless Linux CI set QT_QPA_PLATFORM=offscreen in the workflow; we do
    not force it here because on macOS the offscreen QPA aborts QPixmap
    creation, while the native (cocoa) plugin renders fine in this session.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def isolated_config_dir(tmp_path, monkeypatch):
    """Point config_dir at a per-test scratch dir so tests never touch the
    real OS config location (and each test gets a clean slate)."""
    from coderadio_tray import config

    cfg = tmp_path / "config"
    cfg.mkdir()

    def _config_dir():
        return cfg

    monkeypatch.setattr(config, "config_dir", _config_dir)
    monkeypatch.setattr(config, "config_path", lambda: cfg / "config.json")
    # single_instance imports config_dir by name, so patch it there too.
    from coderadio_tray import single_instance

    monkeypatch.setattr(single_instance, "config_dir", _config_dir, raising=False)
    return cfg
