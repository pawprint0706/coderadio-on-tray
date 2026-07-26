#!/bin/sh
# Build launcher (macOS): double-click in Finder to build the standalone
# .app + DMG release artifact. Runs scripts/build_macos.sh underneath.
cd "$(dirname "$0")"

if [ ! -x scripts/build_macos.sh ]; then
  echo "scripts/build_macos.sh not found. Run this file from the project root."
  read -n 1
  exit 1
fi

bash scripts/build_macos.sh
status=$?

echo
if [ $status -eq 0 ]; then
  echo "Build succeeded. Artifacts in dist/:"
  ls -lh dist/CodeRadioTray.app dist/CodeRadioTray-*.dmg 2>/dev/null
else
  echo "Build failed (exit $status). Scroll up for details."
fi
echo
echo "Press any key to close this window..."
read -n 1
exit $status