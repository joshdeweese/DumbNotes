"""Sidebar list of notes: one line per note, grouped under month headings."""

from datetime import date, datetime

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from .style import HOVER, MUTED, SELECTED, TEXT

ID_ROLE = Qt.ItemDataRole.UserRole
NOTE_ROLE = Qt.ItemDataRole.UserRole + 1
HEADER_ROLE = Qt.ItemDataRole.UserRole + 2
ROW_HEIGHT = 32
HEADER_HEIGHT = 30
GAP = 10  # space between title, tags and date


def month_label(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%B %Y")


def short_ts(iso: str) -> str:
    when = datetime.fromisoformat(iso)
    if when.date() == date.today():
        return when.strftime("Today %H:%M")
    return f"{when.strftime('%b')} {when.day}, {when.strftime('%H:%M')}"


class NoteDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        height = HEADER_HEIGHT if index.data(HEADER_ROLE) else ROW_HEIGHT
        return QSize(option.rect.width(), height)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        header = index.data(HEADER_ROLE)
        if header:
            self._paint_header(painter, option, header)
        else:
            self._paint_note(painter, option, index.data(NOTE_ROLE))
        painter.restore()

    @staticmethod
    def _paint_header(painter, option, text):
        font = QFont(option.font)
        font.setPointSizeF(option.font.pointSizeF() * 0.85)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(MUTED))
        rect = QRectF(option.rect).adjusted(18, 8, -18, -2)
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, text)

    @staticmethod
    def _paint_note(painter, option, note):
        rect = QRectF(option.rect).adjusted(6, 1, -6, -1)
        if option.state & QStyle.StateFlag.State_Selected:
            background = SELECTED
        elif option.state & QStyle.StateFlag.State_MouseOver:
            background = HOVER
        else:
            background = None
        if background:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(rect, 7, 7)

        inner = rect.adjusted(12, 0, -12, 0)
        center = Qt.AlignmentFlag.AlignVCenter
        small = QFont(option.font)
        small.setPointSizeF(option.font.pointSizeF() * 0.85)
        title_metrics, small_metrics = QFontMetrics(option.font), QFontMetrics(small)

        # Date on the right, then the title, then tags in whatever room is left.
        stamp = short_ts(note["modified_at"])
        stamp_width = small_metrics.horizontalAdvance(stamp)
        painter.setFont(small)
        painter.setPen(QColor(MUTED))
        painter.drawText(inner, Qt.AlignmentFlag.AlignRight | center, stamp)

        room = inner.width() - stamp_width - GAP
        title = note["title"] or "Untitled"
        title = title_metrics.elidedText(title, Qt.TextElideMode.ElideRight, int(room))
        title_width = title_metrics.horizontalAdvance(title)
        painter.setFont(option.font)
        painter.setPen(QColor(TEXT if note["title"] else MUTED))
        painter.drawText(QRectF(inner.left(), inner.top(), room, inner.height()),
                         Qt.AlignmentFlag.AlignLeft | center, title)

        tags_room = room - title_width - GAP
        if note["tags"] and tags_room > 30:
            tags = small_metrics.elidedText(note["tags"], Qt.TextElideMode.ElideRight,
                                            int(tags_room))
            painter.setFont(small)
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(inner.left() + title_width + GAP, inner.top(), tags_room,
                                    inner.height()), Qt.AlignmentFlag.AlignLeft | center, tags)
