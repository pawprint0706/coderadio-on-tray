from __future__ import annotations

import plistlib
import sys
from types import SimpleNamespace

import coderadio_tray.startup as startup


def test_macos_login_startup_writes_and_removes_launch_agent(monkeypatch, tmp_path) -> None:
    path = tmp_path / "org.coderadio-on-tray.app.plist"
    monkeypatch.setattr(startup.sys, "platform", "darwin")
    monkeypatch.setattr(startup, "mac_launch_agent_path", lambda: path)
    monkeypatch.setattr(startup, "startup_arguments", lambda: ["/Applications/App", "--flag"])

    startup.set_login_startup(True)

    payload = plistlib.loads(path.read_bytes())
    assert payload["Label"] == "org.coderadio-on-tray.app"
    assert payload["ProgramArguments"] == ["/Applications/App", "--flag"]
    assert payload["RunAtLoad"] is True

    startup.set_login_startup(False)
    assert not path.exists()


def test_unsupported_platform_rejects_enabling_login_startup(monkeypatch) -> None:
    monkeypatch.setattr(startup.sys, "platform", "linux")

    try:
        startup.set_login_startup(True)
    except RuntimeError as exc:
        assert "Windows and macOS" in str(exc)
    else:
        raise AssertionError("expected unsupported login startup to fail")


def test_windows_login_startup_updates_current_user_run_key(monkeypatch) -> None:
    writes: list[tuple] = []
    deletes: list[str] = []

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        REG_SZ=1,
        CreateKey=lambda *_args: Key(),
        SetValueEx=lambda *args: writes.append(args),
        DeleteValue=lambda _key, name: deletes.append(name),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    monkeypatch.setattr(startup.sys, "platform", "win32")
    monkeypatch.setattr(startup, "startup_arguments", lambda: [r"C:\Program Files\App.exe"])

    startup.set_login_startup(True)
    startup.set_login_startup(False)

    assert writes[0][1] == "CodeRadioTray"
    assert '"C:\\Program Files\\App.exe"' in writes[0][4]
    assert deletes == ["CodeRadioTray"]
