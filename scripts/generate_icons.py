#!/usr/bin/env python3
"""Generate app.ico / PNG / macOS iconset from the supplied FCC mark."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from coderadio_tray.ui.icons import _render_app_pixmap, resources_icons_dir  # noqa: E402


def _png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return bytes(ba)


def _write_ico(path: Path, images: list[QImage]) -> None:
    """Write a multi-size ICO (PNG-compressed entries)."""
    entries: list[tuple[int, int, bytes]] = []
    for img in images:
        w, h = img.width(), img.height()
        png = _png_bytes(img)
        entries.append((w if w < 256 else 0, h if h < 256 else 0, png))

    count = len(entries)
    offset = 6 + count * 16
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, count)
    data_blobs: list[bytes] = []
    for w, h, png in entries:
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), offset)
        data_blobs.append(png)
        offset += len(png)
    for blob in data_blobs:
        out += blob
    path.write_bytes(out)


def main() -> int:
    app = QApplication([])
    out = resources_icons_dir()
    out.mkdir(parents=True, exist_ok=True)
    iconset = out / "app.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    by_size: dict[int, QImage] = {}
    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        pm = _render_app_pixmap(size)
        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        by_size[size] = img
        img.save(str(out / f"app-{size}.png"), "PNG")

    iconset_map = {
        16: ["icon_16x16.png"],
        32: ["icon_16x16@2x.png", "icon_32x32.png"],
        64: ["icon_32x32@2x.png"],
        128: ["icon_128x128.png"],
        256: ["icon_128x128@2x.png", "icon_256x256.png"],
        512: ["icon_256x256@2x.png", "icon_512x512.png"],
        1024: ["icon_512x512@2x.png"],
    }
    for size, names in iconset_map.items():
        for name in names:
            by_size[size].save(str(iconset / name), "PNG")

    _write_ico(out / "app.ico", [by_size[s] for s in (16, 32, 48, 64, 128, 256)])
    by_size[256].save(str(out / "app.png"), "PNG")

    print(f"Wrote icons under {out}")
    print("On macOS build: iconutil -c icns app.iconset -o app.icns")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
