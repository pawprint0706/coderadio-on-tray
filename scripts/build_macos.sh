#!/usr/bin/env bash
# Build a standalone macOS release (PyInstaller onedir / .app) with bundled mpv
# and its Homebrew dylibs relocated next to the binary, so the result runs on a
# Mac that has no Python and no Homebrew.
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
  else
    echo "mpv not found at $MPV_SRC and Homebrew unavailable." >&2
    echo "Place a relocatable mpv binary at .tools/mpv/extract/mpv" >&2
    exit 1
  fi
fi

# dylibbundler relocates mpv's Homebrew dylibs into the bundle so the app is
# self-contained. Homebrew install is best-effort (build-time toolchain only).
if ! command -v dylibbundler >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "Installing dylibbundler via Homebrew ..."
    brew install dylibbundler
  else
    echo "dylibbundler not found and Homebrew unavailable; mpv will not be relocatable." >&2
    exit 1
  fi
fi

echo "Ensuring app.icns from campfire iconset ..."
ICONS_DIR="${ROOT}/src/coderadio_tray/resources/icons"
"$PYTHON" scripts/generate_icons.py
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "${ICONS_DIR}/app.iconset" -o "${ICONS_DIR}/app.icns"
else
  echo "iconutil missing; PyInstaller .app may lack a custom Dock/Finder icon." >&2
fi

echo "Running PyInstaller ..."
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/coderadio_tray.spec

bundle_mpv() {
  local dest="$1"
  mkdir -p "${dest}/mpv"
  cp "$MPV_SRC" "${dest}/mpv/mpv"
  chmod +x "${dest}/mpv/mpv"

  # Collect mpv's non-system dylibs into .../mpv/libs and rewrite its load
  # commands to @executable_path/libs/. Ignored locations (/usr/lib,
  # /System/Library) exist on every Mac and are left absolute.
  dylibbundler -od -b -of -ns \
    -x "${dest}/mpv/mpv" \
    -d "${dest}/mpv/libs" \
    -p "@executable_path/libs/" \
    -i /usr/lib -i /System/Library

  # dylibbundler can add @executable_path/libs/ twice (from multiple source
  # rpaths); a duplicate LC_RPATH aborts the process under dyld on launch.
  # Delete duplicates, leaving exactly one rpath entry.
  while [ "$(otool -l "${dest}/mpv/mpv" | grep -c 'LC_RPATH')" -gt 1 ]; do
    install_name_tool -delete_rpath "@executable_path/libs/" "${dest}/mpv/mpv"
  done

  # install_name_tool invalidated the ad-hoc signature; re-sign so the bundle
  # loads. The .app is deep-signed again below to seal it as a whole.
  codesign --force -s - "${dest}/mpv/mpv" 2>/dev/null || true
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
  codesign --force --deep -s - "$APP_DIR" 2>/dev/null || true
  echo "Build OK: $APP_DIR"

  # Wrap the .app into a compressed DMG with an /Applications symlink so the
  # release artifact is a single file users can drag-and-drop install.
  VERSION=$("$PYTHON" -c "from coderadio_tray import __version__; print(__version__)")
  DMG="${ROOT}/dist/CodeRadioTray-${VERSION}-macos.dmg"
  STAGING="$(mktemp -d)"
  cp -R "$APP_DIR" "$STAGING/"
  ln -s /Applications "$STAGING/Applications"
  SIZE_K=$(/usr/bin/du -sk "$STAGING" | awk '{print int($1*1.1+1024)}')
  hdiutil create -srcfolder "$STAGING" -volname CodeRadioTray -fs HFS+ \
    -size "${SIZE_K}k" /tmp/coderadio-rw.dmg >/dev/null 2>&1
  hdiutil convert /tmp/coderadio-rw.dmg -format UDZO -imagekey zlib-level=9 \
    -o "$DMG" >/dev/null 2>&1
  rm -rf "$STAGING" /tmp/coderadio-rw.dmg
  echo "DMG OK: $DMG"
elif [[ -d "$ONEDIR" ]]; then
  bundle_mpv "$ONEDIR"
  echo "Build OK: $ONEDIR"
  echo "Tip: add --windowed BUNDLE options on macOS PyInstaller if you need a .app wrapper."
else
  echo "No dist output found" >&2
  exit 1
fi

du -sh dist/CodeRadioTray* 2>/dev/null || true