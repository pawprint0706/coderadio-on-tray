# Linux support (best-effort)

Code Radio on Tray’s **primary platforms are Windows and macOS**. Linux is supported
on a best-effort basis: the same Python/Qt/mpv code paths run, but system tray
behavior varies by desktop environment (DE) and is not part of the release QA matrix.

## What works in principle

| Area | Expectation |
|------|-------------|
| Playback / metadata | Same as Win/mac (`mpv` + AzuraCast HTTP) |
| Config | `~/.config/coderadio-on-tray/` (or `$XDG_CONFIG_HOME`) |
| Tray + popup | Depends on StatusNotifier / AppIndicator support |
| Single instance | `QLockFile` under the config dir |
| Dev run | `python -m pip install -e .` then `python -m coderadio_tray --console` |

There is **no** Linux AppImage / packaging script in v0.3.x. Users are expected to
install Python 3.11+, system `mpv`, and run from a venv (or wait for a future package).

## Known DE caveats

- **GNOME**: tray icons often need an extension (e.g. AppIndicator / legacy tray).
- **KDE Plasma / XFCE / Cinnamon**: usually fine for `QSystemTrayIcon` + popup.
- Left/right click semantics can differ under some indicator backends.
- Wayland vs X11 may affect popup positioning relative to the tray.

See also `docs/considerations.md` §3.1.

## How we would run an Ubuntu smoke (when someone has a machine)

This is the procedure to use for a one-distro smoke — **not automated in CI**
(CI only runs headless unit tests with `QT_QPA_PLATFORM=offscreen`).

### 1. Machine

- Fresh **Ubuntu 24.04 LTS** (or 22.04) desktop VM or spare PC  
- Pick one DE to record: default GNOME, or install `kubuntu-desktop` / XFCE for a
  second data point if desired

### 2. Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip mpv \
  libegl1 libgl1  # Qt offscreen / some GL stacks
# Optional for GNOME tray visibility:
# sudo apt install gnome-shell-extension-appindicator
```

### 3. Run from source

```bash
git clone https://github.com/pawprint0706/coderadio-on-tray.git
cd coderadio-on-tray
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m coderadio_tray --console
```

### 4. Checklist (fill results in notes / issue)

| Step | Pass? |
|------|-------|
| Tray icon appears (or note extension required) | |
| Left click play/pause | |
| Right click popup (volume / bitrate / quit) | |
| Stream audio plays via mpv | |
| Bitrate 128 ↔ 64 without reconnect loop | |
| Second instance shows “already running” | |
| Quit leaves no orphan `mpv` / python | |

### 5. Report

Open a GitHub issue with: Ubuntu version, DE, Wayland/X11, checklist results, and
logs from the `--console` session. Fixes stay **best-effort / community-priority**.

---

*Documented for P2. Not a support commitment for all Linux DEs.*
