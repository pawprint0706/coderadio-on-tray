from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygonF


def _render_pixmap(size: int, *, playing: bool, error: bool) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, size // 16)
    if error:
        fill = QColor("#B33A3A")
    elif playing:
        fill = QColor("#2F6FED")
    else:
        fill = QColor("#4A5568")

    painter.setBrush(fill)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)

    painter.setBrush(QColor("#FFFFFF"))
    if playing:
        bar_w = max(2, size // 8)
        gap = max(1, size // 16)
        total = bar_w * 2 + gap
        x0 = (size - total) // 2
        y0 = size // 4
        h = size // 2
        painter.drawRoundedRect(x0, y0, bar_w, h, 1, 1)
        painter.drawRoundedRect(x0 + bar_w + gap, y0, bar_w, h, 1, 1)
    else:
        tri = QPolygonF(
            [
                QPointF(size * 0.38, size * 0.28),
                QPointF(size * 0.38, size * 0.72),
                QPointF(size * 0.72, size * 0.5),
            ]
        )
        painter.drawPolygon(tri)

    painter.end()
    return pixmap


def make_tray_icon(*, playing: bool = False, error: bool = False) -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(_render_pixmap(size, playing=playing, error=error))
    return icon
