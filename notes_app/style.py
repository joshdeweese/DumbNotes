"""Colours and stylesheet: a grey sidebar beside the writing pane, no boxes. Light and dark.

Code reads colours from `C` (e.g. C.TEXT) when it draws, so switching theme with
set_theme() and re-applying stylesheet() changes everything.
"""

import tempfile
from pathlib import Path
from string import Template
from types import SimpleNamespace

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

LIGHT = {
    "SIDEBAR": "#F5F4F0",
    "EDITOR": "#FFFFFF",
    "TEXT": "#29261B",
    "MUTED": "#87857D",
    "LINE": "#E8E6DF",
    "FIELD": "#EBE9E3",
    "HOVER": "#ECEAE4",
    "SELECTED": "#E3E0D7",
    "ACCENT": "#C96442",
    "ACCENT_HOVER": "#B4573A",
    "FOCUS": "#D9B8A6",
    "DISABLED": "#BDBBB3",
    "DANGER_BG": "#F8E6E0",
    "DANGER_TEXT": "#A8402A",
    "TEXT_SELECTION": "#F2D7C9",
    "SCROLL": "#D8D6CF",
    "SCROLL_HOVER": "#C4C2BA",
    "CHECKBOX": "#B9B6AC",
}

DARK = {
    "SIDEBAR": "#1F1E1C",
    "EDITOR": "#262624",
    "TEXT": "#ECEBE6",
    "MUTED": "#9A988F",
    "LINE": "#3B3A36",
    "FIELD": "#32312E",
    "HOVER": "#2F2E2B",
    "SELECTED": "#3C3B37",
    "ACCENT": "#D97757",
    "ACCENT_HOVER": "#E38A6C",
    "FOCUS": "#8A5A47",
    "DISABLED": "#5E5C56",
    "DANGER_BG": "#4A2A22",
    "DANGER_TEXT": "#F0A08A",
    "TEXT_SELECTION": "#5A3A2E",
    "SCROLL": "#4A4944",
    "SCROLL_HOVER": "#5C5B55",
    "CHECKBOX": "#7A786F",
}

THEMES = {"light": LIGHT, "dark": DARK}
ICON_GREY = "#87857D"  # the colour the toolbar icons are drawn in; replaced by C.MUTED

C = SimpleNamespace(**LIGHT, name="light")
HERE = Path(__file__).parent


def set_theme(name: str) -> None:
    C.__dict__.update(THEMES[name], name=name)


def is_dark() -> bool:
    return C.name == "dark"


def themed_svg(file_name: str, color: str | None = None) -> bytes:
    """An icon's SVG with its grey swapped for the theme's (or the given) colour."""
    svg = (HERE / file_name).read_text()
    for grey in (ICON_GREY, LIGHT["CHECKBOX"]):
        svg = svg.replace(grey, color or (C.MUTED if grey == ICON_GREY else C.CHECKBOX))
    return svg.encode()


def themed_icon(file_name: str, size: tuple[int, int]) -> QIcon:
    renderer = QSvgRenderer(QByteArray(themed_svg(file_name)))
    icon = QIcon()
    for scale in (1, 2):  # sharp on Retina screens too
        pixmap = QPixmap(size[0] * scale, size[1] * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        icon.addPixmap(pixmap)
    return icon


def themed_svg_file(file_name: str) -> str:
    """Path to a copy of an icon in the theme's colours, for use in rich text (<img src>)."""
    path = Path(tempfile.gettempdir()) / f"dumbnotes-{C.name}-{file_name}"
    data = themed_svg(file_name)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return path.as_posix()


STYLESHEET = Template("""
QWidget { color: $TEXT; }
QMainWindow, QDialog { background: $EDITOR; }
#sidebar { background: $SIDEBAR; }
#editorPane { background: $EDITOR; }
QSplitter::handle { background: $LINE; }

QLineEdit, QComboBox {
    background: $FIELD; border: 1px solid transparent; border-radius: 8px;
    padding: 6px 10px; selection-background-color: $FOCUS; selection-color: $TEXT;
}
QLineEdit:focus, QComboBox:focus, QComboBox:on { background: $EDITOR; border-color: $FOCUS; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: $EDITOR; border: 1px solid $LINE; padding: 4px; outline: none;
    selection-background-color: $HOVER; selection-color: $TEXT;
}

QPushButton {
    background: $FIELD; border: none; border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: $SELECTED; }
QPushButton:disabled { color: $DISABLED; background: transparent; }
QPushButton#primary { background: $ACCENT; color: white; font-weight: 600; }
QPushButton#primary:hover { background: $ACCENT_HOVER; }
QPushButton#flat { background: transparent; color: $MUTED; text-align: left; padding: 7px 10px; }
QPushButton#flat:hover { background: $HOVER; color: $TEXT; }
QPushButton#danger { background: transparent; color: $MUTED; padding: 5px 10px; }
QPushButton#danger:hover { background: $DANGER_BG; color: $DANGER_TEXT; }

#notesList { background: transparent; border: none; outline: none; padding: 0; }

QPushButton#tagChip { background: $FIELD; color: $TEXT; border-radius: 10px; padding: 3px 9px; }
QPushButton#tagChip:hover { background: $DANGER_BG; color: $DANGER_TEXT; }
QPushButton#addTag { background: transparent; color: $MUTED; padding: 3px 8px; }
QPushButton#addTag:hover { background: $HOVER; color: $TEXT; }
#tagPicker { background: $EDITOR; border: 1px solid $LINE; border-radius: 8px; }
#tagPickerList { background: transparent; border: none; padding: 0; }
#editor { background: $EDITOR; border: none; selection-background-color: $TEXT_SELECTION;
          selection-color: $TEXT; }
#hint { color: $MUTED; }
QPushButton#markdownBtn { background: transparent; padding: 6px 8px; }
QPushButton#markdownBtn:hover { background: $HOVER; }
QPushButton#markdownBtn:checked { background: $SELECTED; }
#cheatSheet { background: $EDITOR; border: 1px solid $LINE; border-radius: 10px; }
#cheatTitle { font-weight: 600; padding-left: 4px; }
#cheatSheet #hint { padding-left: 4px; font-size: 11px; }
#snippetList { background: transparent; }
#snippet { border-radius: 7px; }
#snippet:hover { background: $HOVER; }
QPushButton#attachBtn { background: transparent; color: $MUTED; padding: 3px 8px 3px 6px; }
QPushButton#attachBtn:hover { background: $HOVER; color: $TEXT; }

QListWidget {
    background: $EDITOR; border: 1px solid $LINE; border-radius: 8px; padding: 4px; outline: none;
}
QListWidget::item { padding: 7px 8px; border-radius: 6px; }
QListWidget::item:hover { background: $HOVER; }
QListWidget::item:selected { background: $SELECTED; color: $TEXT; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $SCROLL; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $SCROLL_HOVER; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenuBar { background: $SIDEBAR; color: $TEXT; }
QMenuBar::item:selected { background: $HOVER; }
QMenu { background: $EDITOR; border: 1px solid $LINE; padding: 4px; }
QMenu::item { padding: 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: $HOVER; }
QMenu::separator { height: 1px; background: $LINE; margin: 4px 8px; }
QToolTip { background: $TEXT; color: $EDITOR; border: none; padding: 4px 8px; }
""")


def stylesheet() -> str:
    return STYLESHEET.substitute(C.__dict__)


def apply_theme(app, name: str) -> None:
    """Switch the whole app to the light or dark theme."""
    set_theme(name)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if name == "dark"
                                    else Qt.ColorScheme.Light)
    app.setStyleSheet(stylesheet())
