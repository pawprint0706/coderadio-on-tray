#!/bin/sh
# Build launcher (macOS): double-click in Finder to build the standalone
# .app + DMG release artifact. Runs scripts/build_macos.sh underneath.

# Resolve this file's directory regardless of how Finder/Terminal launched it.
# $0 may be empty / just "build_macos.command" / relative / absolute depending
# on the Terminal "shells -run command" wrapper; cover all of them and fall back
# to searching a known list of likely project roots.
src="${BASH_SOURCE:-$0}"
case "$src" in
  /*) dir=$(dirname "$src") ;;
  ''|build_macos.command) dir="$PWD" ;;
  *)  dir=$(dirname "$PWD/$src") ;;
esac

# If the resolved dir doesn't actually contain scripts/, search a few common
# roots (the file's own inode via lsof is overkill; user paths are predictable).
if [ ! -f "$dir/scripts/build_macos.sh" ]; then
  for cand in \
      "$PWD" \
      "$HOME/Projects/coderadio-on-tray" \
      "$(dirname "$dir")" ; do
    if [ -f "$cand/scripts/build_macos.sh" ]; then
      dir="$cand"
      break
    fi
  done
fi

cd "$dir" || { echo "cd failed: $dir" >&2; exit 1; }

if [ ! -f scripts/build_macos.sh ]; then
  echo "scripts/build_macos.sh not found under: $dir" >&2
  echo "PWD=$(pwd)  \$0=[$0]  BASH_SOURCE=[${BASH_SOURCE:-<unset>}]" >&2
  exit 1
fi

# Make the build tools the script invokes discoverable even when Finder launches
# this .command with a minimal environment (no Homebrew /usr/local/bin etc.).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

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
echo "Press Return to close this window..."
read -r _ || true
exit $status