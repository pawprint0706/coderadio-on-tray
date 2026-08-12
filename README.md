# Code Radio on Tray

Unofficial [freeCodeCamp Code Radio](https://coderadio.freecodecamp.org/) player that lives in the system tray / menu bar.

**Not affiliated with freeCodeCamp.** Streams and metadata come from their public AzuraCast endpoints.

| | |
|--|--|
| Version | 0.5.1 |
| Platforms | Windows / macOS (primary), Linux best-effort |
| Stack | Python 3.11+, PySide6, mpv (JSON IPC) |

## Requirements (development)

- Python 3.11+
- [mpv](https://mpv.io/) on `PATH`, or under `.tools/mpv/extract/`
- Windows / macOS primarily tested; Linux is best-effort (see [Linux](#linux-best-effort) below)

```bash
# Windows example
winget install shinchiro.mpv
```

Tray and app icons use the supplied freeCodeCamp primary mark. The playing state and
main app icon show the complete mark; paused/stopped shows its two original brackets
with the center campfire removed. freeCodeCamp and its logo are trademarks of the
freeCodeCamp organization; this remains an unofficial, unaffiliated client.

Development validates mpv with `mpv --version` and resolves it in this order:
an explicit `mpv_path`, the active `PATH`, then the `.tools` cache. Release builds use
the pinned policy in `packaging/mpv-versions.json`; Windows verifies the archive SHA256,
while macOS verifies the pinned Homebrew formula revision (Homebrew verifies its bottle SHA256).

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

The popup shows album artwork and the current listener count when available. Its Settings page
controls login startup, startup playback, GitHub release notifications, artwork/listener
visibility, and whether tray/menu-bar left click toggles playback or opens/closes the popup.

By default, playback starts after the first successful metadata fetch. Only one instance is allowed.

Settings: OS config dir → `coderadio-on-tray/config.json`  
(volume, bitrate, poll interval, UI/startup preferences, first-run hint flag, optional `mpv_path`).

## Standalone release (no Python install)

Hard requirement from the design docs: end users run a bundled folder/app **without** installing Python or mpv.

Pushing a version tag (`v*`, matching `__version__`) runs [.github/workflows/release.yml](.github/workflows/release.yml):
macOS DMG + Windows setup.exe are built on GitHub Actions and attached to the GitHub Release
(with `SHA256SUMS-v*.txt`). Linux stays best-effort from source.

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

#### Windows SmartScreen / “Unknown publisher”

Builds are **not code-signed** (no certificate planned). Windows Defender SmartScreen or
Edge/Chrome download warnings are expected for a new/unsigned publisher.

**If the installer is blocked:**

1. Prefer the asset from [GitHub Releases](https://github.com/pawprint0706/coderadio-on-tray/releases) only.
2. Verify integrity against the release `SHA256SUMS-*.txt` (or the hash listed in release notes):

```powershell
Get-FileHash .\CodeRadioTray-0.5.1-win64-setup.exe -Algorithm SHA256
```

3. When SmartScreen shows **Windows protected your PC**:
   - Click **More info**
   - Click **Run anyway**
4. Browser “download is not commonly downloaded” / “keep anyway”: use **Keep** / **Keep anyway**, then run the `.exe` and follow step 3 if SmartScreen appears again.
5. If your org policy blocks unsigned installers entirely, use a machine where you can approve the prompt, or run from source (`pip install -e .`).

After install, the Start Menu / desktop shortcut and tray use the freeCodeCamp mark.

### macOS

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

Output under `dist/` (`.app` / DMG). Dock icon is suppressed (`LSUIElement` + runtime Accessory policy); Finder still shows the generated freeCodeCamp `.icns` when built with `iconutil`.

#### macOS Gatekeeper / quarantine

Builds are **not signed or notarized**. First open after download from the web often hits Gatekeeper.

**If macOS says the app can’t be opened / was blocked:**

1. Download only from [GitHub Releases](https://github.com/pawprint0706/coderadio-on-tray/releases).
2. Verify SHA256:

```bash
shasum -a 256 CodeRadioTray-0.5.1-macos.dmg
```

3. **Preferred UI path:** in Finder, **Control-click** (right-click) the app → **Open** → confirm **Open** in the dialog. Do this once; later launches are remembered for that user.
4. Or clear quarantine after you trust the SHA256 match:

```bash
# DMG mount path or Applications copy — adjust the path
xattr -dr com.apple.quarantine "/Applications/Code Radio Tray.app"
```

5. System Settings → Privacy & Security may show an **Open Anyway** button shortly after a blocked launch — use that if Control-click Open is unavailable.
6. Corporate MDM that forbids unsigned apps: run from source with `pip install -e ".[macos]"` instead.

> Homebrew `mpv` may pull shared libraries — for a truly portable Mac build, prefer a relocatable/static mpv binary under `.tools/mpv/extract/mpv` and verify with `otool -L` on a clean machine.

### Linux (best-effort)

No packaged Linux binary in v0.5.x. Primary QA remains Windows + macOS. For source install,
DE caveats, and a concrete **Ubuntu smoke checklist**, see
[`docs/linux-best-effort.md`](docs/linux-best-effort.md).

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
- `docs/linux-best-effort.md` — Linux caveats + Ubuntu smoke procedure
- `docs/review-v0.1.md` / `docs/review-v0.2.md` / `docs/review-v0.3.md` — archived implementation reviews
- `docs/review-v0.5.md` — current **0.5.0** implementation and release-readiness review
- `docs/smoke-sleep-network.md` — sleep / network reconnect smoke checklist (results blank until filled)

## License

MIT. Unofficial client; respect freeCodeCamp / Code Radio usage norms. Do not mirror stream URLs for redistribution.
