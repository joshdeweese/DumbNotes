"""Plain text editor with pasted images shown inline.

The note is saved as plain text; each image is written as a Markdown link such as
![|400](images/abc.png), where 400 is the width it was resized to.
"""

import re
import uuid
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QFont, QImage, QPainter, QPen, QPixmap, QSyntaxHighlighter,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextImageFormat)
from PySide6.QtWidgets import QInputDialog, QMenu, QTextEdit

from .file_store import IMAGE_LINK

FONT_SIZE = 12
TITLE_SIZE = 16
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
HANDLE = 12  # size of the drag-to-resize square on an image's bottom-right corner
MIN_IMAGE_WIDTH = 20
TEXT_COLUMN_WIDTH = 760
BULLET = re.compile(r"^(\s*)([-*])(\s+)(.*)$")
INDENT = "  "
OBJECT = "\ufffc"  # the character Qt puts in the text where an image sits


def document_to_text(doc: QTextDocument) -> str:
    """The document as plain text, with each image written as a Markdown link."""
    lines = []
    block = doc.begin()
    while block.isValid():
        parts = []
        text_list = block.textList()
        if text_list is not None:  # only in notes brought over from the old format
            parts.append(INDENT * (text_list.format().indent() - 1) + "- ")
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            fmt = fragment.charFormat()
            if fmt.isImageFormat():
                image = fmt.toImageFormat()
                width = f"|{round(image.width())}" if image.width() else ""
                parts.append(f"![{width}]({image.name()})" * len(fragment.text()))
            else:
                parts.append(fragment.text().replace("\u2028", "\n"))
            it += 1
        lines.append("".join(parts))
        block = block.next()
    return "\n".join(lines)


class TitleHighlighter(QSyntaxHighlighter):
    """Shows the note's first line larger and bold. Only the display changes."""

    def __init__(self, doc: QTextDocument):
        super().__init__(doc)
        self.fmt = QTextCharFormat()
        self.fmt.setFontPointSize(TITLE_SIZE)
        self.fmt.setFontWeight(QFont.Weight.DemiBold)

    def highlightBlock(self, text: str) -> None:
        # Block state 1 means the title has been reached at or before this block.
        if self.previousBlockState() == 1:
            self.setCurrentBlockState(1)
            return
        if not text.replace(OBJECT, "").strip():
            self.setCurrentBlockState(0)
            return
        self.setCurrentBlockState(1)
        for match in re.finditer(f"[^{OBJECT}]+", text):  # leave images alone
            self.setFormat(match.start(), match.end() - match.start(), self.fmt)


class NoteEditor(QTextEdit):
    MAX_IMAGE_WIDTH = 640

    def __init__(self, notes_dir: Path, parent=None):
        super().__init__(parent)
        self.notes_dir = notes_dir
        self.images_dir = notes_dir / "images"
        self.setAcceptRichText(False)
        font = self.document().defaultFont()
        font.setPointSize(FONT_SIZE)
        self.document().setDefaultFont(font)
        self.highlighter = TitleHighlighter(self.document())
        # Image under the mouse as (document position, rect), and the drag in progress.
        self._hover: tuple[int, QRectF] | None = None
        self._drag: dict | None = None
        self._natural_sizes: dict = {}
        self.viewport().setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(self._clear_hover)
        self.document().contentsChanged.connect(self._clear_hover)

    def resizeEvent(self, event):
        # Keep the text in a comfortable centred column on wide windows.
        side = max(28, (event.size().width() - TEXT_COLUMN_WIDTH) // 2)
        self.setViewportMargins(side, 12, side, 12)
        super().resizeEvent(event)

    # --- text -------------------------------------------------------------

    def set_text(self, text: str) -> None:
        """Show a note, turning its image links into the images themselves."""
        doc = self.document()
        doc.setUndoRedoEnabled(False)
        self.clear()
        cursor = QTextCursor(doc)
        plain = QTextCharFormat()
        for i, line in enumerate(text.split("\n")):
            if i:
                cursor.insertBlock()
            pos = 0
            for match in IMAGE_LINK.finditer(line):
                cursor.insertText(line[pos:match.start()], plain)
                self._insert_image_link(cursor, match.group(2).strip(), match.group(1))
                pos = match.end()
            cursor.insertText(line[pos:], plain)
        doc.setUndoRedoEnabled(True)
        self.setTextCursor(QTextCursor(doc))

    def _insert_image_link(self, cursor: QTextCursor, name: str, alt: str) -> None:
        fmt = QTextImageFormat()
        fmt.setName(name)
        width = re.search(r"(?:^|\|)\s*(\d+)\s*$", alt)
        natural = self._natural_size(fmt)
        if width and not natural.isEmpty():
            w = int(width.group(1))
            fmt.setWidth(w)
            fmt.setHeight(natural.height() * w / natural.width())
        cursor.insertImage(fmt)

    def text(self) -> str:
        return document_to_text(self.document())

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        key = event.key()
        bullet = BULLET.match(cursor.block().text())
        if bullet and not cursor.hasSelection():
            indent, marker, space, content = bullet.groups()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not content.strip():
                    # Enter on an empty bullet ends the list (or steps out a level).
                    self._replace_line(cursor, indent[:-len(INDENT)] + marker + space
                                       if indent else "")
                else:
                    cursor.insertText("\n" + indent + marker + space)
                    self.ensureCursorVisible()
                return
            if key == Qt.Key.Key_Tab:
                self._indent_line(cursor, 1)
                return
            if key == Qt.Key.Key_Backtab:  # Shift+Tab
                self._indent_line(cursor, -1)
                return
        super().keyPressEvent(event)

    def _replace_line(self, cursor: QTextCursor, text: str) -> None:
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def _indent_line(self, cursor: QTextCursor, delta: int) -> None:
        """Nest (+1) or un-nest (-1) a bullet by adding or removing two spaces in front."""
        start = QTextCursor(cursor.block())
        if delta > 0:
            start.insertText(INDENT)
        elif cursor.block().text().startswith(INDENT):
            start.movePosition(QTextCursor.MoveOperation.NextCharacter,
                               QTextCursor.MoveMode.KeepAnchor, len(INDENT))
            start.removeSelectedText()

    # --- images -----------------------------------------------------------

    def canInsertFromMimeData(self, source):
        return source.hasImage() or source.hasUrls() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            self.insert_image(image)
            return
        if source.hasUrls():
            paths = [Path(u.toLocalFile()) for u in source.urls() if u.isLocalFile()]
            images = [p for p in paths if p.suffix.lower() in IMAGE_SUFFIXES]
            if images:
                for path in images:
                    self.insert_image(QImage(str(path)))
                return
        # Paste text without outside fonts/colours so notes stay consistent.
        self.insertPlainText(source.text())

    def insert_image(self, image: QImage) -> None:
        if image.isNull():
            return
        self.images_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{uuid.uuid4().hex}.png"
        image.save(str(self.images_dir / file_name), "PNG")
        fmt = QTextImageFormat()
        fmt.setName(f"images/{file_name}")  # relative to the notes folder
        if image.width() > self.MAX_IMAGE_WIDTH:
            fmt.setWidth(self.MAX_IMAGE_WIDTH)
            fmt.setHeight(image.height() * self.MAX_IMAGE_WIDTH / image.width())
        self.textCursor().insertImage(fmt)

    def _image_cursor(self, position: int) -> QTextCursor | None:
        """Cursor selecting the image at a document position, if one is there."""
        if position < 0:
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter,
                            QTextCursor.MoveMode.KeepAnchor)
        return cursor if cursor.charFormat().isImageFormat() else None

    def _image_rect(self, cursor: QTextCursor) -> QRectF:
        """Where the selected image is drawn, in viewport coordinates."""
        position = cursor.selectionStart()
        size = self._display_size(cursor.charFormat().toImageFormat())
        block = self.document().findBlock(position)
        line = block.layout().lineForTextPosition(position - block.position())
        line_top = (self.document().documentLayout().blockBoundingRect(block).top()
                    + line.y() - self.verticalScrollBar().value())
        start = QTextCursor(self.document())
        start.setPosition(position)
        left = self.cursorRect(start).left()
        # Images sit on the text baseline.
        return QRectF(left, line_top + line.ascent() - size.height(), size.width(), size.height())

    def image_at(self, pos, margin: float = 0) -> QTextCursor | None:
        """Cursor selecting the image under a viewport position, if there is one."""
        hit = self.cursorForPosition(pos).position()
        for p in (hit, hit - 1):
            cursor = self._image_cursor(p)
            if cursor is not None:
                rect = self._image_rect(cursor).adjusted(-margin, -margin, margin, margin)
                if rect.contains(pos.toPointF()):
                    return cursor
        return None

    def _natural_size(self, fmt: QTextImageFormat):
        name = fmt.name()
        if name not in self._natural_sizes:
            self._natural_sizes[name] = QImage(str(self.notes_dir / name)).size()
        return self._natural_sizes[name]

    def _display_size(self, fmt: QTextImageFormat) -> QSizeF:
        natural = QSizeF(self._natural_size(fmt))
        if fmt.width() and fmt.height():
            return QSizeF(fmt.width(), fmt.height())
        return natural

    @staticmethod
    def _handle_rect(rect: QRectF) -> QRectF:
        return QRectF(rect.right() - HANDLE / 2, rect.bottom() - HANDLE / 2, HANDLE, HANDLE)

    # --- drag to resize ---------------------------------------------------

    def _clear_hover(self) -> None:
        if self._hover is not None and self._drag is None:
            self._hover = None
            self.viewport().unsetCursor()
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            self.viewport().update()

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton and self._hover is not None
                and self._handle_rect(self._hover[1]).contains(event.position())):
            position, rect = self._hover
            self._drag = {"position": position, "rect": rect,
                          "start_x": event.position().x(), "width": rect.width()}
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag is not None:
            rect = self._drag["rect"]
            width = rect.width() + pos.x() - self._drag["start_x"]
            self._drag["width"] = max(MIN_IMAGE_WIDTH, min(width, 4000))
            self.viewport().update()
            return
        cursor = self.image_at(pos.toPoint(), margin=HANDLE / 2)
        hover = (cursor.selectionStart(), self._image_rect(cursor)) if cursor else None
        if hover != self._hover:
            self._hover = hover
            self.viewport().update()
        on_handle = hover is not None and self._handle_rect(hover[1]).contains(pos)
        self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor if on_handle
                                  else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            drag, self._drag = self._drag, None
            cursor = self._image_cursor(drag["position"])
            if cursor is not None:
                self.resize_image(cursor, round(drag["width"]))
            self._clear_hover()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._clear_hover()
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover is None and self._drag is None:
            return
        painter = QPainter(self.viewport())
        color = self.palette().highlight().color()
        if self._drag is not None:
            rect = self._drag["rect"]
            scale = self._drag["width"] / rect.width()
            preview = QRectF(rect.topLeft(), QSizeF(rect.width() * scale, rect.height() * scale))
            painter.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
            painter.drawRect(preview)
            painter.drawText(preview.bottomLeft() + QPointF(0, 14), f"{round(preview.width())} px")
        else:
            rect = self._hover[1]
            painter.setPen(QPen(color, 1))
            painter.drawRect(rect)
            painter.fillRect(self._handle_rect(rect), color)

    def resize_image(self, cursor: QTextCursor, width: int | None) -> None:
        """Set an image's display width, keeping its shape; None means original size."""
        fmt = cursor.charFormat().toImageFormat()
        natural = self._natural_size(fmt)
        if natural.isEmpty():
            return
        width = width or natural.width()
        fmt.setWidth(width)
        fmt.setHeight(natural.height() * width / natural.width())
        cursor.setCharFormat(fmt)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        image = self.image_at(event.pos())
        if image is not None:
            fit = self.viewport().width() - 2 * int(self.document().documentMargin()) - 4
            sizes = [("Small", 200), ("Medium", 400), ("Large", 640), ("Fit to width", fit),
                     ("Original size", None)]
            first = menu.actions()[0] if menu.actions() else None
            size_menu = QMenu("Image size", menu)
            for label, width in sizes:
                size_menu.addAction(label, lambda w=width: self.resize_image(image, w))
            size_menu.addAction("Custom width…", lambda: self._custom_width(image))
            menu.insertMenu(first, size_menu)
            menu.insertSeparator(first)
        menu.exec(event.globalPos())

    def _custom_width(self, cursor: QTextCursor) -> None:
        current = int(cursor.charFormat().toImageFormat().width()) or 400
        width, ok = QInputDialog.getInt(self, "Image size", "Width in pixels:", current, 20, 4000)
        if ok:
            self.resize_image(cursor, width)

    def loadResource(self, resource_type, url: QUrl):
        # Image links are relative to the notes folder.
        path = self.notes_dir / url.toString()
        if url.isRelative() and path.is_file():
            return QImage(str(path))
        return super().loadResource(resource_type, url)
