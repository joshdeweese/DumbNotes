"""Markdown cheat sheet in the note list panel: click an example to insert it into the note."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from .style import ACCENT, FIELD, LINE, MUTED

MONO = "Menlo, Consolas, monospace"
CHECKBOX = (Path(__file__).with_name("checkbox.svg")).as_posix()


@dataclass(frozen=True)
class Snippet:
    """Markdown to insert: before + placeholder + after. The placeholder is left selected
    (or replaced by the selected text). Line snippets go at the start of a line."""
    name: str
    html: str  # how the example looks in the cheat sheet
    before: str
    placeholder: str = ""
    after: str = ""
    line: bool = False
    cursor_after: int | None = None  # when wrapping a selection, put the cursor this far into `after`


SNIPPETS = [
    Snippet("Heading 1", '<span style="font-size:17pt; font-weight:700;">Heading 1</span>',
            "# ", line=True),
    Snippet("Heading 2", '<span style="font-size:14pt; font-weight:700;">Heading 2</span>',
            "## ", line=True),
    Snippet("Heading 3", '<span style="font-size:12pt; font-weight:700;">Heading 3</span>',
            "### ", line=True),
    Snippet("Bold", "<b>Bold text</b>", "**", "bold text", "**"),
    Snippet("Italic", "<i>Italic text</i>", "*", "italic text", "*"),
    Snippet("Blockquote", f'<span style="color:{LINE};">▌</span>&nbsp;'
                          f'<i style="color:{MUTED};">A quote</i>', "> ", line=True),
    Snippet("Unordered list", "•&nbsp; List item", "- ", line=True),
    Snippet("Task list", f'<img src="{CHECKBOX}" width="14" height="14" '
                         f'style="vertical-align:middle;">&nbsp; Task item', "- [ ] ", line=True),
    Snippet("Inline code", f'<span style="font-family:{MONO}; background:{FIELD};">'
                           f'&nbsp;inline code&nbsp;</span>', "`", "code", "`"),
    Snippet("Code block", f'<table width="100%" cellpadding="5"><tr><td style="background:'
                          f'{FIELD}; font-family:{MONO};">code block</td></tr></table>',
            "```\n", "code", "\n```", line=True),
    Snippet("Horizontal rule", f'<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                               f'<td style="background:{LINE}; font-size:1pt;">&nbsp;</td>'
                               f'</tr></table>', "---\n", line=True),
    Snippet("Link", f'<span style="color:{ACCENT}; text-decoration:underline;">Link text</span>',
            "[", "link text", "](https://)", cursor_after=len("](https://")),
]


class SnippetButton(QFrame):
    clicked = Signal(object)

    def __init__(self, snippet: Snippet, parent=None):
        super().__init__(parent, objectName="snippet")
        self.snippet = snippet
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        markdown = (snippet.before + snippet.placeholder + snippet.after).replace("\n", " ⏎ ")
        self.setToolTip(f"{snippet.name}: inserts  {markdown.strip()}")
        label = QLabel(snippet.html, objectName="snippetLabel")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.addWidget(label)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.clicked.emit(self.snippet)
        super().mouseReleaseEvent(event)


class CheatSheet(QFrame):
    """Clickable Markdown examples; `insert` fires with the Snippet that was clicked."""

    insert = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent, objectName="cheatSheet")
        title = QLabel("Markdown", objectName="cheatTitle")
        hint = QLabel("Click to add to your note", objectName="hint")
        items = QWidget(objectName="snippetList")
        items_layout = QVBoxLayout(items)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(2)
        for snippet in SNIPPETS:
            button = SnippetButton(snippet)
            button.clicked.connect(self.insert)
            items_layout.addWidget(button)
        items_layout.addStretch(1)
        scroll = QScrollArea(objectName="snippetScroll", widgetResizable=True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(items)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(2)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(4)
        layout.addWidget(scroll, 1)
