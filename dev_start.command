#!/bin/sh
# Dev launcher (macOS): double-click in Finder to run Code Radio Tray.
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 not found. Install Python 3.11+ (e.g. brew install python@3.12)."
  read -n 1
  exit 1
}

if [ ! -d .venv ]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi

echo "Installing deps ..."
.venv/bin/python -m pip install -q -e ".[macos]"

echo "Starting Code Radio Tray (Ctrl+C to quit) ..."
exec .venv/bin/python -m coderadio_tray --console