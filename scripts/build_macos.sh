#!/usr/bin/env bash
# Build a standalone macOS release (PyInstaller onedir / .app) with bundled mpv
# and its Homebrew dylibs relocated next to the binary, so the result runs on a
# Mac that has no Python and no Homebrew.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILD_STARTED=$SECONDS

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
  PYTHON="${ROOT}/.venv/bin/python"
fi

echo "[1/5] Installing package + PyInstaller + macOS extras ..."
"$PYTHON" -m pip install -q -e ".[dev,macos]"

MPV_SRC="${ROOT}/.tools/mpv/extract/mpv"
MPV_POLICY="${ROOT}/packaging/mpv-versions.json"
MPV_FORMULA=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["macos"]["homebrew_formula"])' "$MPV_POLICY")
MPV_EXPECTED=$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["macos"]["formula_version"])' "$MPV_POLICY")
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required to obtain the pinned macOS mpv build." >&2
  exit 1
fi
brew list "$MPV_FORMULA" >/dev/null 2>&1 || brew install "$MPV_FORMULA"
MPV_ACTUAL=$(brew list --versions "$MPV_FORMULA" | awk '{print $2}')
if [[ "$MPV_ACTUAL" != "$MPV_EXPECTED" ]]; then
  echo "Pinned mpv formula mismatch: expected $MPV_EXPECTED, installed $MPV_ACTUAL." >&2
  echo "Update packaging/mpv-versions.json deliberately before building." >&2
  exit 1
fi
MPV_BREW="$(brew --prefix "$MPV_FORMULA")/bin/mpv"
if ! "$MPV_BREW" --version >/dev/null 2>&1; then
  echo "Homebrew mpv failed its --version probe: $MPV_BREW" >&2
  exit 1
fi
mkdir -p "$(dirname "$MPV_SRC")"
cp "$MPV_BREW" "$MPV_SRC"
chmod +x "$MPV_SRC"
if ! "$MPV_SRC" --version >/dev/null 2>&1; then
  echo "Copied mpv failed its --version probe: $MPV_SRC" >&2
  exit 1
fi
echo "Using pinned Homebrew mpv $MPV_ACTUAL (bottle SHA256 verified by Homebrew)."

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

echo "[2/5] Generating app icons ..."
ICONS_DIR="${ROOT}/src/coderadio_tray/resources/icons"
"$PYTHON" scripts/generate_icons.py
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "${ICONS_DIR}/app.iconset" -o "${ICONS_DIR}/app.icns"
else
  echo "iconutil missing; PyInstaller .app may lack a custom Dock/Finder icon." >&2
fi

echo "[3/5] Running PyInstaller (this is the longest step) ..."
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/coderadio_tray.spec

bundle_mpv() {
  local dest="$1"
  local dylib_log="${ROOT}/build/dylibbundler.log"
  mkdir -p "${dest}/mpv"
  cp "$MPV_SRC" "${dest}/mpv/mpv"
  chmod +x "${dest}/mpv/mpv"

  # Collect mpv's non-system dylibs into .../mpv/libs and rewrite its load
  # commands to @executable_path/libs/. Ignored locations (/usr/lib,
  # /System/Library) exist on every Mac and are left absolute.
  echo "[4/5] Bundling mpv dylibs (about 47 libraries; please wait) ..."
  if ! dylibbundler -od -b -of -ns \
      -x "${dest}/mpv/mpv" \
      -d "${dest}/mpv/libs" \
      -p "@executable_path/libs/" \
      -i /usr/lib -i /System/Library >"$dylib_log" 2>&1; then
    echo "mpv dylib bundling failed:" >&2
    cat "$dylib_log" >&2
    return 1
  fi

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
  VERSION=$("$PYTHON" -c "from coderadio_tray import __version__; print(__version__)")
  if [[ -f "$PLIST" ]] && command -v /usr/libexec/PlistBuddy >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
      || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null \
      || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null \
      || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST"
  fi
  codesign --force --deep -s - "$APP_DIR" 2>/dev/null || true
  echo "App bundle OK: $APP_DIR (version $VERSION)"

  # Wrap the .app into a compressed DMG with an /Applications symlink so the
  # release artifact is a single file users can drag-and-drop install.
  echo "[5/5] Creating compressed DMG ..."
  DMG="${ROOT}/dist/CodeRadioTray-${VERSION}-macos.dmg"
  DMG_WORK="$(mktemp -d)"
  STAGING="${DMG_WORK}/staging"
  RW_DMG="${DMG_WORK}/CodeRadioTray-rw.dmg"
  DMG_LOG="${DMG_WORK}/hdiutil.log"
  cleanup_dmg() {
    rm -rf "$DMG_WORK"
  }
  trap cleanup_dmg EXIT

  mkdir -p "$STAGING"
  cp -R "$APP_DIR" "$STAGING/"
  ln -s /Applications "$STAGING/Applications"
  SIZE_K=$(/usr/bin/du -sk "$STAGING" | awk '{print int($1*1.1+1024)}')

  if ! hdiutil create -srcfolder "$STAGING" -volname CodeRadioTray -fs HFS+ \
      -size "${SIZE_K}k" -ov "$RW_DMG" >"$DMG_LOG" 2>&1; then
    echo "DMG create failed:" >&2
    cat "$DMG_LOG" >&2
    exit 1
  fi

  rm -f "$DMG"
  if ! hdiutil convert "$RW_DMG" -format UDZO -imagekey zlib-level=9 \
      -ov -o "$DMG" >"$DMG_LOG" 2>&1; then
    echo "DMG convert failed:" >&2
    cat "$DMG_LOG" >&2
    exit 1
  fi

  cleanup_dmg
  trap - EXIT
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
echo "Completed in $((SECONDS - BUILD_STARTED)) seconds."
