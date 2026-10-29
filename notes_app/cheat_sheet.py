"""Markdown cheat sheet shown in the lower half of the note list panel."""

from html import escape

from PySide6.QtWidgets import QFrame, QLabel, QTextBrowser, QVBoxLayout

from .style import ACCENT, FIELD, LINE, MUTED, TEXT

MONO = "Menlo, Consolas, monospace"

# (element, what you type, how it shows) - the last is HTML.
ROWS = [
    ("Headings", "# Heading 1\n## Heading 2\n### Heading 3",
     '<span style="font-size:17pt; font-weight:700;">Heading 1</span><br>'
     '<span style="font-size:14pt; font-weight:700;">Heading 2</span><br>'
     '<span style="font-size:12pt; font-weight:700;">Heading 3</span>'),
    ("Bold", "**bold text**", "<b>bold text</b>"),
    ("Italic", "*italic text*", "<i>italic text</i>"),
    ("Blockquote", "> a quote",
     f'<span style="color:{LINE};">▌</span> <i style="color:{MUTED};">a quote</i>'),
    ("Unordered list", "- First item\n- Second item\n  - Nested item",
     "•&nbsp; First item<br>•&nbsp; Second item<br>&nbsp;&nbsp;&nbsp;◦&nbsp; Nested item"),
    ("Code", "`inline code`\n```\ncode block\n```",
     f'<span style="font-family:{MONO}; background:{FIELD};">&nbsp;inline code&nbsp;</span>'
     f'<table cellpadding="4" style="margin-top:6px;" width="100%"><tr>'
     f'<td style="background:{FIELD}; font-family:{MONO};">code block</td></tr></table>'),
    ("Horizontal rule", "---",
     f'<table width="100%" cellspacing="0" cellpadding="0"><tr>'
     f'<td style="background:{LINE}; font-size:1pt;">&nbsp;</td></tr></table>'),
    ("Link", "[title](https://x.com)",
     f'<span style="color:{ACCENT}; text-decoration:underline;">title</span>'),
]


def cheat_sheet_html() -> str:
    rows = []
    for i, (element, markdown, result) in enumerate(ROWS):
        shade = "#FAF9F6" if i % 2 == 0 else "#FFFFFF"
        code = escape(markdown).replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
        rows.append(
            f'<tr style="background:{shade};">'
            f'<td width="52%" valign="top">'
            f'<div style="color:{MUTED}; font-size:8pt; font-weight:600;">{element.upper()}</div>'
            f'<div style="font-family:{MONO}; font-size:9.5pt; color:{TEXT};">{code}</div></td>'
            f'<td width="48%" valign="middle" style="color:{TEXT};">{result}</td></tr>')
    header = (f'<tr><td style="color:{MUTED}; font-size:8pt; font-weight:600;">YOU TYPE</td>'
              f'<td style="color:{MUTED}; font-size:8pt; font-weight:600;">SHOWS AS</td></tr>')
    return (f'<table width="100%" cellspacing="0" cellpadding="7">{header}{"".join(rows)}'
            f'</table>')


class CheatSheet(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, objectName="cheatSheet")
        title = QLabel("Markdown cheat sheet", objectName="cheatTitle")
        view = QTextBrowser(objectName="cheatView", openLinks=False)
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setHtml(cheat_sheet_html())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(title)
        layout.addWidget(view, 1)
