# Code Radio on Tray

Unofficial [freeCodeCamp Code Radio](https://coderadio.freecodecamp.org/) player that lives in the system tray / menu bar.

**Not affiliated with freeCodeCamp.** Streams and metadata come from their public AzuraCast endpoints.

| | |
|--|--|
| Version | 0.3.0 |
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
Build machine also needs [Inno Setup](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup` — the script installs it if missing).

| Output | Role |
|--------|------|
| `dist\CodeRadioTray-*-win64-setup.exe` | **배포용** 설치 마법사 (권장) |
| `dist\CodeRadioTray\` | 포터블 onedir (개발/디버그) |

설치 마법사는 **관리자 권한 없이** 사용자 폴더에 설치합니다:

`%LOCALAPPDATA%\Programs\CodeRadioTray`  
(예: `C:\Users\<you>\AppData\Local\Programs\CodeRadioTray`)

- Program Files에 넣지 않음 (UAC 불필요)
- 시작 메뉴 바로가기 + 선택적 바탕화면 아이콘
- 설정(`%APPDATA%\coderadio-on-tray`)은 제거해도 남음

**Unsigned** 빌드는 SmartScreen 경고가 날 수 있습니다 — “More info → Run anyway”.  
코드 서명은 계획하지 않습니다. 다운로드 후 [GitHub Releases](https://github.com/pawprint0706/coderadio-on-tray/releases)의 **SHA256**으로 무결성을 확인하세요.

```powershell
Get-FileHash .\CodeRadioTray-0.3.0-win64-setup.exe -Algorithm SHA256
```

### macOS

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Output under `dist/` (`.app` when PyInstaller emits a bundle). Dock icon is suppressed (`LSUIElement` + runtime Accessory policy). Gatekeeper may block unsigned apps: right-click → Open, or `xattr -dr com.apple.quarantine …`.  
코드 서명/공증은 계획하지 않습니다 — Release의 SHA256으로 검증하세요.

```bash
shasum -a 256 CodeRadioTray-0.3.0-macos.dmg
```

> Homebrew `mpv` may pull shared libraries — for a truly portable Mac build, prefer a relocatable/static mpv binary under `.tools/mpv/extract/mpv` and verify with `otool -L` on a clean machine.

### Smoke checklist (clean PC / Mac)

1. No Python / no system mpv on PATH.
2. **Windows:** run `CodeRadioTray-*-win64-setup.exe` → install under `%LOCALAPPDATA%\Programs\CodeRadioTray` (no admin).  
   **macOS:** open the DMG → drag to Applications (or run from the volume).
3. Launch once — tray/menu-bar icon appears, stream plays.
4. Second launch shows “already running” and exits.
5. Switch 128 ↔ 64 kbps without reconnect loops.
6. Quit from the popup; no leftover `mpv` / app process.
7. **Windows:** uninstall from Settings → Apps (per-user entry).

## Tests

```bash
python -m pip install -e ".[dev]"
pytest
```

## Docs

- `docs/considerations.md` — design decisions
- `docs/review-v0.1.md` / `docs/review-v0.2.md` / `docs/review-v0.3.md` — implementation reviews
- `docs/smoke-sleep-network.md` — sleep / network reconnect smoke checklist (results blank until filled)

## License

MIT. Unofficial client; respect freeCodeCamp / Code Radio usage norms. Do not mirror stream URLs for redistribution.
