"""Live Markdown preview: every line except the one being edited is shown formatted.

Only the display changes; the note's text (and file) stays plain Markdown. Markdown symbols
on formatted lines are hidden by drawing them invisibly with letter spacing that cancels
their width. The editor draws the extras text styling can't do: bullets, checkboxes,
quote bars, rules and code block backgrounds (see LineKind and NoteEditor.paintEvent).
"""

import re

from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QSyntaxHighlighter, QTextCharFormat,
                           QTextDocument)

from .style import ACCENT, FIELD, MUTED

TITLE_SIZE = 22
HEADING_SIZES = {1: 20, 2: 17, 3: 15}  # h4-h6 are bold at normal size
OBJECT = "￼"  # the character Qt puts in the text where an image sits
MONO = "Menlo, Consolas, monospace"

HEADING = re.compile(r"^(#{1,6})(\s+)")
QUOTE = re.compile(r"^>\s?")
RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
CHECKBOX = re.compile(r"^(\s*)([-*+])(\s+)\[([ xX])\](\s)")
BULLET = re.compile(r"^(\s*)([-*+])(\s+)")
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
URL = re.compile(r"https?://[^\s<>()]+[^\s<>().,;:!?'\"]")
BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
ITALIC = re.compile(r"(?<![*\w])([*_])(?=[^\s*_])(.+?)(?<=[^\s*_])\1(?![*\w])")
STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")

# Block state bits, carried from line to line.
TITLE_SEEN = 1
IN_CODE = 2
CODE_LINE = 4  # this line is part of a ``` code block (the editor shades it)


class LineKind:
    """What the editor should draw for a formatted line (read from its text)."""

    @staticmethod
    def rule(text: str) -> bool:
        return bool(RULE.match(text))

    @staticmethod
    def checkbox(text: str) -> re.Match | None:
        return CHECKBOX.match(text)

    @staticmethod
    def bullet(text: str) -> re.Match | None:
        return None if LineKind.rule(text) or CHECKBOX.match(text) else BULLET.match(text)

    @staticmethod
    def quote(text: str) -> re.Match | None:
        return QUOTE.match(text)


def link_at(text: str, index: int) -> str | None:
    """The URL of the Markdown link or bare web address covering text[index], if any."""
    for match in LINK.finditer(text):
        if match.start() <= index < match.end():
            return match.group(2)
    for match in URL.finditer(text):
        if match.start() <= index < match.end():
            return match.group()
    return None


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, doc: QTextDocument):
        super().__init__(doc)
        self.raw_block: int | None = None  # the line being edited, shown as plain text

    def highlightBlock(self, text: str) -> None:
        prev = max(self.previousBlockState(), 0)
        state = prev & (TITLE_SEEN | IN_CODE)
        raw = self.currentBlock().blockNumber() == self.raw_block
        styles = [QTextCharFormat() for _ in text]
        hidden = [False] * len(text)

        if prev & IN_CODE or FENCE.match(text):
            if FENCE.match(text):
                state ^= IN_CODE
            self.setCurrentBlockState(state | CODE_LINE)
            self._style(styles, 0, len(text), family=MONO)
            if FENCE.match(text) and not raw:
                self._hide(hidden, 0, len(text))  # the ``` lines show as blank shaded rows
            self._apply(text, styles, hidden)
            return

        is_title = not prev & TITLE_SEEN and bool(text.replace(OBJECT, "").strip())
        if is_title:
            state |= TITLE_SEEN
        self.setCurrentBlockState(state)

        if raw:
            if is_title:  # keep the title its size while editing it, so it doesn't jump
                self._style(styles, 0, len(text), size=TITLE_SIZE, bold=True)
                self._apply(text, styles, hidden)
            return

        self._format_line(text, styles, hidden)
        if is_title:
            self._style(styles, 0, len(text), size=TITLE_SIZE, bold=True)
        self._apply(text, styles, hidden)

    # --- formatting a line ------------------------------------------------

    def _format_line(self, text: str, styles: list, hidden: list) -> None:
        if LineKind.rule(text):
            self._style(styles, 0, len(text), color=QColor(0, 0, 0, 0))  # editor draws a line
            return
        start = 0
        heading = HEADING.match(text)
        if heading:
            level = len(heading.group(1))
            self._hide(hidden, 0, heading.end())
            self._style(styles, 0, len(text), bold=True, size=HEADING_SIZES.get(level))
            start = heading.end()
        elif QUOTE.match(text):
            end = QUOTE.match(text).end()
            self._style(styles, 0, end, color=QColor(0, 0, 0, 0))  # editor draws a bar here
            self._style(styles, end, len(text), italic=True, color=MUTED)
            start = end
        elif LineKind.checkbox(text):
            box = LineKind.checkbox(text)
            self._hide(hidden, box.start(2), box.start(4) - 1)  # the "- "
            self._style(styles, box.start(4) - 1, box.end(4) + 1, color=QColor(0, 0, 0, 0))
            if box.group(4) != " ":
                self._style(styles, box.end(), len(text), strike=True, color=MUTED)
            start = box.end()
        elif LineKind.bullet(text):
            bullet = LineKind.bullet(text)
            self._style(styles, bullet.start(2), bullet.end(2), color=QColor(0, 0, 0, 0))
            start = bullet.end()
        self._format_inline(text, start, styles, hidden)

    def _format_inline(self, text: str, start: int, styles: list, hidden: list) -> None:
        taken = [False] * len(text)  # inside code spans, where nothing else applies

        for match in CODE_SPAN.finditer(text, start):
            ticks = len(match.group(1))
            self._hide(hidden, match.start(), match.start() + ticks)
            self._hide(hidden, match.end() - ticks, match.end())
            self._style(styles, match.start(), match.end(), family=MONO, background=FIELD)
            taken[match.start():match.end()] = [True] * (match.end() - match.start())

        def free(m: re.Match) -> bool:
            return not any(taken[m.start():m.end()])

        for match in LINK.finditer(text, start):
            if free(match):
                self._hide(hidden, match.start(), match.start() + 1)
                self._hide(hidden, match.end(1), match.end())
                self._style(styles, match.start(1), match.end(1), color=ACCENT, underline=True)
                taken[match.start():match.end()] = [True] * (match.end() - match.start())
        for match in URL.finditer(text, start):
            if free(match):
                self._style(styles, match.start(), match.end(), color=ACCENT, underline=True)
        for match in BOLD.finditer(text, start):
            if free(match):
                self._hide(hidden, match.start(), match.start() + 2)
                self._hide(hidden, match.end() - 2, match.end())
                self._style(styles, match.start(), match.end(), bold=True)
        for match in ITALIC.finditer(text, start):
            if free(match):
                self._hide(hidden, match.start(), match.start() + 1)
                self._hide(hidden, match.end() - 1, match.end())
                self._style(styles, match.start(), match.end(), italic=True)
        for match in STRIKE.finditer(text, start):
            if free(match):
                self._hide(hidden, match.start(), match.start() + 2)
                self._hide(hidden, match.end() - 2, match.end())
                self._style(styles, match.start(), match.end(), strike=True)

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _style(styles: list, start: int, end: int, *, bold=False, italic=False, strike=False,
               underline=False, size=None, family=None, color=None, background=None) -> None:
        for fmt in styles[start:end]:
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            if strike:
                fmt.setFontStrikeOut(True)
            if underline:
                fmt.setFontUnderline(True)
            if size:
                fmt.setFontPointSize(size)
            if family:
                fmt.setFontFamilies([f.strip() for f in family.split(",")])
            if color is not None:
                fmt.setForeground(QColor(color))
            if background:
                fmt.setBackground(QColor(background))

    @staticmethod
    def _hide(hidden: list, start: int, end: int) -> None:
        hidden[start:end] = [True] * (end - start)

    def _apply(self, text: str, styles: list, hidden: list) -> None:
        base = self.document().defaultFont()
        for i, (fmt, hide) in enumerate(zip(styles, hidden)):
            if text[i] == OBJECT:
                continue  # leave images alone
            if hide:
                # Invisible, with letter spacing that cancels the character's own width.
                font = fmt.font().resolve(base)
                fmt.setForeground(QColor(0, 0, 0, 0))
                fmt.setBackground(QColor(0, 0, 0, 0))
                fmt.setFontUnderline(False)
                fmt.setFontStrikeOut(False)
                fmt.setFontLetterSpacingType(QFont.SpacingType.AbsoluteSpacing)
                fmt.setFontLetterSpacing(-QFontMetricsF(font).horizontalAdvance(text[i]))
            elif not fmt.properties():
                continue
            self.setFormat(i, 1, fmt)
