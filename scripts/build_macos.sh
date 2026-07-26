#!/usr/bin/env bash
# Build a macOS release (PyInstaller onedir / .app) with bundled mpv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
  PYTHON="${ROOT}/.venv/bin/python"
fi

echo "Installing package + PyInstaller + macOS extras ..."
"$PYTHON" -m pip install -q -e ".[dev,macos]"

MPV_SRC="${ROOT}/.tools/mpv/extract/mpv"
if [[ ! -f "$MPV_SRC" ]]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Fetching mpv via Homebrew (copy binary into .tools) ..."
    brew list mpv >/dev/null 2>&1 || brew install mpv
    MPV_BREW="$(brew --prefix mpv)/bin/mpv"
    mkdir -p "$(dirname "$MPV_SRC")"
    cp "$MPV_BREW" "$MPV_SRC"
    echo "Note: Homebrew mpv may need shared libs — verify with otool -L on a clean Mac."
  else
    echo "mpv not found at $MPV_SRC and Homebrew unavailable." >&2
    echo "Place a relocatable mpv binary at .tools/mpv/extract/mpv" >&2
    exit 1
  fi
fi

echo "Running PyInstaller ..."
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/coderadio_tray.spec

bundle_mpv() {
  local dest="$1"
  mkdir -p "${dest}/mpv"
  cp "$MPV_SRC" "${dest}/mpv/mpv"
  chmod +x "${dest}/mpv/mpv"
}

APP_DIR="${ROOT}/dist/CodeRadioTray.app"
ONEDIR="${ROOT}/dist/CodeRadioTray"

if [[ -d "$APP_DIR" ]]; then
  bundle_mpv "${APP_DIR}/Contents/MacOS"
  PLIST="${APP_DIR}/Contents/Info.plist"
  if [[ -f "$PLIST" ]] && command -v /usr/libexec/PlistBuddy >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
      || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
  fi
  echo "Build OK: $APP_DIR"
elif [[ -d "$ONEDIR" ]]; then
  bundle_mpv "$ONEDIR"
  echo "Build OK: $ONEDIR"
  echo "Tip: add --windowed BUNDLE options on macOS PyInstaller if you need a .app wrapper."
else
  echo "No dist output found" >&2
  exit 1
fi

du -sh dist/CodeRadioTray* 2>/dev/null || true
