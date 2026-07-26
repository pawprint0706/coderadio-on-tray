# Code Radio on Tray

Unofficial [freeCodeCamp Code Radio](https://coderadio.freecodecamp.org/) player that lives in the system tray / menu bar.

**Not affiliated with freeCodeCamp.** Streams and metadata come from their public AzuraCast endpoints.

| | |
|--|--|
| Version | 0.2.0 |
| Platforms | Windows / macOS (primary), Linux best-effort |
| Stack | Python 3.11+, PySide6, mpv (JSON IPC) |

## Requirements (development)

- Python 3.11+
- [mpv](https://mpv.io/) on `PATH`, or under `.tools/mpv/extract/`
- Windows / macOS primarily tested; Linux is best-effort (DE tray differences possible)

```bash
# Windows example
winget install shinchiro.mpv
```

## Run (development)

```powershell
cd coderadio-on-tray
python -m pip install -e .

# One-click launchers
# Windows:  dev_start.bat
# macOS:    open dev_start.command   # installs .[macos] for Dock-hide

# Console debug (Ctrl+C to quit):
python -m coderadio_tray --console
```

macOS menu-bar-only mode needs the Cocoa bridge:

```bash
python -m pip install -e ".[macos]"
```

### Tray icon not visible? (Windows)

1. Click the **^** overflow in the taskbar notification area.
2. Windows **Settings → System → Notifications → Other system tray icons** → enable **Code Radio Tray**.
3. A balloon hint appears **once** on first run.

### Stuck process

```powershell
taskkill /IM mpv.exe /F
taskkill /IM CodeRadioTray.exe /F
taskkill /IM python.exe /F
taskkill /IM pythonw.exe /F
```

## Controls

| Input | Action |
|-------|--------|
| Tray left click | Play / Pause |
| Tray right click | Non-modal popup (track, volume, bitrate, quit) |

Auto-starts playback after the first successful metadata fetch. Only one instance is allowed.

Settings: OS config dir → `coderadio-on-tray/config.json`  
(volume, bitrate, poll interval, first-run hint flag, optional `mpv_path`).

## Standalone release (no Python install)

Hard requirement from the design docs: end users run a bundled folder/app **without** installing Python or mpv.

### Windows

```powershell
# Double-click, or:
build_windows.bat

# Equivalent:
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Needs `.tools\mpv\extract\mpv.exe` (or the script runs `scripts\fetch_mpv_windows.ps1`).
Output: `dist\CodeRadioTray\`

| Path | Role |
|------|------|
| `CodeRadioTray.exe` | App (windowed) |
| `mpv\mpv.exe` | Bundled player |
| `_internal\` | Python / Qt runtime |

Zip that folder for distribution (~240 MB including bundled mpv). **Unsigned** builds may trigger SmartScreen — “More info → Run anyway”, or prefer hashes from GitHub Releases.

### macOS

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Output under `dist/` (`.app` when PyInstaller emits a bundle). Dock icon is suppressed (`LSUIElement` + runtime Accessory policy). Gatekeeper may block unsigned apps: right-click → Open, or `xattr -dr com.apple.quarantine …`.

> Homebrew `mpv` may pull shared libraries — for a truly portable Mac build, prefer a relocatable/static mpv binary under `.tools/mpv/extract/mpv` and verify with `otool -L` on a clean machine.

### Smoke checklist (clean PC / Mac)

1. No Python / no system mpv on PATH.
2. Launch the release binary once — tray icon appears, stream plays.
3. Second launch shows “already running” and exits.
4. Switch 128 ↔ 64 kbps without reconnect loops.
5. Quit from the popup; no leftover `mpv` / app process.

## Tests

```bash
python -m pip install -e ".[dev]"
pytest
```

## Docs

- `docs/considerations.md` — design decisions
- `docs/review-v0.1.md` / `docs/review-v0.2.md` — implementation reviews

## License

MIT. Unofficial client; respect freeCodeCamp / Code Radio usage norms. Do not mirror stream URLs for redistribution.
