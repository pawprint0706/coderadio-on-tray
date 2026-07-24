# Code Radio on Tray

Unofficial [freeCodeCamp Code Radio](https://coderadio.freecodecamp.org/) player that lives in the system tray / menu bar.

**Not affiliated with freeCodeCamp.** Streams and metadata come from their public AzuraCast endpoints.

## Requirements (development)

- Python 3.11+
- [mpv](https://mpv.io/) on `PATH` (bundled in release builds later)
- Windows / macOS primarily tested; Linux is best-effort

```bash
# Windows example
winget install shinchiro.mpv
```

## Run

```powershell
cd D:\DEV\PP\coderadio-on-tray
python -m pip install -e .

# Recommended: no console window (uses pythonw via gui-scripts after install)
coderadio-tray-gui

# Or:
pythonw -m coderadio_tray

# Debug (keep console, Ctrl+C to quit):
python -m coderadio_tray --console
```

### Tray icon not visible?

1. Click the **^** overflow in the taskbar notification area.
2. Windows **Settings → System → Notifications → Other system tray icons** → enable **Code Radio Tray**.
3. A one-time balloon may point you to the icon.

### Stuck process (no tray / can't quit)

```powershell
taskkill /IM mpv.exe /F
taskkill /IM python.exe /F
taskkill /IM pythonw.exe /F
```

## Controls (v0.1)

| Input | Action |
|-------|--------|
| Tray left click | Play / Pause |
| Tray right click | Non-modal popup |

Auto-starts playback after the first successful metadata fetch.

Settings: OS config dir → `coderadio-on-tray/config.json`.

## Stack

- PySide6 tray + non-modal popup
- mpv via JSON IPC
- AzuraCast nowplaying API (`coderadio-admin-v2`)

See `docs/considerations.md` for design decisions.
