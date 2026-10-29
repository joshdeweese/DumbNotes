"""Plain text editor with pasted images shown inline and live Markdown formatting.

The note is saved as plain text; each image is written as a Markdown link such as
![|400](images/abc.png), where 400 is the width it was resized to. Every line except the one
being edited is shown with its Markdown formatted (see markdown.py).
"""

import re
import uuid
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QDesktopServices, QImage, QPainter, QPen, QPixmap,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextImageFormat)
from PySide6.QtWidgets import QInputDialog, QMenu, QTextEdit

from .file_store import IMAGE_LINK
from .markdown import CODE_LINE, LineKind, MarkdownHighlighter, link_at
from .style import ACCENT, FIELD, LINE, TEXT

FONT_SIZE = 12
BULLET_GLYPHS = "•◦▪"  # by nesting level
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
HANDLE = 12  # size of the drag-to-resize square on an image's bottom-right corner
MIN_IMAGE_WIDTH = 20
TEXT_COLUMN_WIDTH = 760
BULLET = re.compile(r"^(\s*)([-*])(\s+)(.*)$")
TASK = re.compile(r"^\[[ xX]\](\s+)")
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


class NoteEditor(QTextEdit):
    MAX_IMAGE_WIDTH = 640

    def __init__(self, parent=None):
        super().__init__(parent)
        self.note_dir: Path | None = None  # image links are relative to this
        self.setAcceptRichText(False)
        font = self.document().defaultFont()
        font.setPointSize(FONT_SIZE)
        self.document().setDefaultFont(font)
        self.highlighter = MarkdownHighlighter(self.document())
        self.cursorPositionChanged.connect(self._update_raw_line)
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
        self.setViewportMargins(side, 0, side, 12)
        super().resizeEvent(event)

    # --- text -------------------------------------------------------------

    def set_text(self, text: str, note_dir: Path) -> None:
        """Show a note, turning its image links into the images themselves."""
        self.note_dir = note_dir
        self.highlighter.raw_block = None
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
        self._update_raw_line()

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
            task = TASK.match(content)  # "- [ ] ..." continues as another unticked task
            if task:
                space, content = space + "[ ]" + task.group(1), content[task.end():]
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

    # --- live markdown ----------------------------------------------------

    def insert_snippet(self, snippet) -> None:
        """Insert Markdown from the cheat sheet at the cursor.

        Text in between the symbols is the selection if there is one (so selecting a word and
        clicking Bold makes it bold), otherwise a placeholder left selected to type over.
        Line snippets (headings, lists, ...) start a new line if the cursor is mid-line.
        """
        cursor = self.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        if OBJECT in selected:  # don't wrap images; add after the selection instead
            cursor.setPosition(cursor.selectionEnd())
            selected = ""
        middle = selected or snippet.placeholder
        cursor.beginEditBlock()
        if selected:
            cursor.removeSelectedText()
        before = snippet.before
        if snippet.line and cursor.block().text()[:cursor.positionInBlock()].strip():
            before = "\n" + before
            while cursor.block().text()[cursor.positionInBlock():][:1] == " ":
                cursor.deleteChar()  # the text moved to the new line shouldn't start with a space
        after = snippet.after
        if snippet.line and snippet.after and cursor.block().text()[cursor.positionInBlock():]:
            after += "\n"  # e.g. a code block's closing ``` gets a line of its own
        cursor.insertText(before)
        start = cursor.position()
        cursor.insertText(middle)
        end = cursor.position()
        cursor.insertText(after)
        cursor.endEditBlock()
        if middle and not selected:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        elif selected and snippet.cursor_after is not None:
            cursor.setPosition(end + snippet.cursor_after)  # e.g. ready to type a link's address
        elif middle:
            cursor.setPosition(end)
        self.setTextCursor(cursor)
        self.setFocus()

    def _update_raw_line(self) -> None:
        """Show the line being edited as plain text and every other line formatted."""
        line = self.textCursor().blockNumber() if self.hasFocus() else None
        old = self.highlighter.raw_block
        if line == old:
            return
        self.highlighter.raw_block = line
        for number in (old, line):
            block = self.document().findBlockByNumber(number) if number is not None else None
            if block is not None and block.isValid():
                self.highlighter.rehighlightBlock(block)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._update_raw_line()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if event.reason() != Qt.FocusReason.PopupFocusReason:  # e.g. the right-click menu
            self._update_raw_line()

    def _visible_blocks(self):
        """(block, rect in viewport coordinates) for each line on screen."""
        block = self.cursorForPosition(QPoint(0, 0)).block()
        layout = self.document().documentLayout()
        dx, dy = -self.horizontalScrollBar().value(), -self.verticalScrollBar().value()
        while block.isValid():
            rect = layout.blockBoundingRect(block).translated(dx, dy)
            if rect.top() > self.viewport().height():
                break
            yield block, rect
            block = block.next()

    def _char_rect(self, position: int) -> QRectF:
        """Where the character at a document position is drawn."""
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        left = self.cursorRect(cursor)
        cursor.setPosition(position + 1)
        right = self.cursorRect(cursor)
        return QRectF(left.left(), left.top(), right.left() - left.left(), left.height())

    def _checkbox_rect(self, block) -> QRectF | None:
        box = LineKind.checkbox(block.text())
        if box is None or block.blockNumber() == self.highlighter.raw_block:
            return None
        left = self._char_rect(block.position() + box.start(4) - 1)
        right = self._char_rect(block.position() + box.end(4))
        size = min(left.height() * 0.62, right.right() - left.left())
        return QRectF(left.left() + (right.right() - left.left() - size) / 2,
                      left.center().y() - size / 2, size, size)

    def _paint_code_backgrounds(self) -> None:
        painter = QPainter(self.viewport())
        margin = self.document().documentMargin()
        for block, rect in self._visible_blocks():
            if block.userState() > 0 and block.userState() & CODE_LINE:
                painter.fillRect(rect.adjusted(margin - 6, 0, -margin, 0), QColor(FIELD))

    def _paint_markdown(self) -> None:
        """Draw what text styling can't: bullets, checkboxes, quote bars and rules."""
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = self.document().documentMargin()
        for block, rect in self._visible_blocks():
            if block.blockNumber() == self.highlighter.raw_block:
                continue
            if block.userState() > 0 and block.userState() & CODE_LINE:
                continue
            text, start = block.text(), block.position()
            if LineKind.rule(text):
                y = rect.center().y()
                painter.setPen(QPen(QColor(LINE), 1.5))
                painter.drawLine(QPointF(rect.left() + margin, y), QPointF(rect.right() - margin, y))
            elif LineKind.quote(text):
                bar = self._char_rect(start)
                painter.fillRect(QRectF(bar.left() + 1, rect.top() + 2, 3, rect.height() - 4),
                                 QColor(LINE))
            elif LineKind.checkbox(text):
                box = self._checkbox_rect(block)
                checked = LineKind.checkbox(text).group(4) != " "
                painter.setPen(QPen(QColor(ACCENT if checked else "#B9B6AC"), 1.3))
                painter.setBrush(QColor(ACCENT) if checked else Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box, 3, 3)
                if checked:
                    painter.setPen(QPen(QColor("white"), 1.6))
                    s, x, y = box.width(), box.left(), box.top()
                    painter.drawPolyline([QPointF(x + s * .25, y + s * .52),
                                          QPointF(x + s * .43, y + s * .70),
                                          QPointF(x + s * .76, y + s * .32)])
                painter.setBrush(Qt.BrushStyle.NoBrush)
            elif LineKind.bullet(text):
                bullet = LineKind.bullet(text)
                level = len(bullet.group(1).expandtabs(len(INDENT))) // len(INDENT)
                painter.setPen(QColor(TEXT))
                painter.drawText(self._char_rect(start + bullet.start(2)),
                                 Qt.AlignmentFlag.AlignCenter,
                                 BULLET_GLYPHS[level % len(BULLET_GLYPHS)])

    def _toggle_checkbox_at(self, pos: QPointF) -> bool:
        block = self.cursorForPosition(pos.toPoint()).block()
        box = self._checkbox_rect(block)
        if box is None or not box.adjusted(-3, -3, 3, 3).contains(pos):
            return False
        mark = LineKind.checkbox(block.text())
        cursor = QTextCursor(self.document())
        cursor.setPosition(block.position() + mark.start(4))
        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter,
                            QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(" " if mark.group(4) != " " else "x")
        return True

    def _open_link_at(self, pos: QPoint) -> bool:
        cursor = self.cursorForPosition(pos)
        url = link_at(cursor.block().text(), cursor.positionInBlock())
        if url is None:
            url = link_at(cursor.block().text(), cursor.positionInBlock() - 1)
        if url is None:
            return False
        QDesktopServices.openUrl(QUrl(url if "://" in url else f"https://{url}"))
        return True

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
        images_dir = self.note_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{uuid.uuid4().hex}.png"
        image.save(str(images_dir / file_name), "PNG")
        fmt = QTextImageFormat()
        fmt.setName(f"images/{file_name}")  # relative to the note's folder
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
        path = str(self.note_dir / name)
        if path not in self._natural_sizes:
            self._natural_sizes[path] = QImage(path).size()
        return self._natural_sizes[path]

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
        if event.button() == Qt.MouseButton.LeftButton:
            if self._toggle_checkbox_at(event.position()):
                return
            # Cmd+click (Ctrl+click on Windows) opens a link.
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier and self._open_link_at(
                    event.position().toPoint()):
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
        self._paint_code_backgrounds()
        super().paintEvent(event)
        self._paint_markdown()
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
        # Image links are relative to the note's folder.
        path = self.note_dir / url.toString() if self.note_dir else None
        if url.isRelative() and path is not None and path.is_file():
            return QImage(str(path))
        return super().loadResource(resource_type, url)
