from __future__ import annotations

import argparse

from coderadio_tray.app import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Code Radio system tray player")
    parser.add_argument(
        "--console",
        action="store_true",
        help="Keep the console window visible (debug)",
    )
    args = parser.parse_args()
    raise SystemExit(run(hide_console=not args.console))


if __name__ == "__main__":
    main()
