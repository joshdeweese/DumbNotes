"""Colours and stylesheet: light grey sidebar, white writing pane, no boxes."""

from pathlib import Path
from string import Template

SIDEBAR = "#F5F4F0"
EDITOR = "#FFFFFF"
TEXT = "#29261B"
MUTED = "#87857D"
LINE = "#E8E6DF"
FIELD = "#EBE9E3"
HOVER = "#ECEAE4"
SELECTED = "#E3E0D7"
ACCENT = "#C96442"
ACCENT_HOVER = "#B4573A"
FOCUS = "#D9B8A6"

CHEVRON = Path(__file__).with_name("chevron-down.svg").as_posix()

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
QComboBox::down-arrow { image: url($CHEVRON); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: $EDITOR; border: 1px solid $LINE; padding: 4px; outline: none;
    selection-background-color: $HOVER; selection-color: $TEXT;
}

QPushButton {
    background: $FIELD; border: none; border-radius: 8px; padding: 7px 14px;
}
QPushButton:hover { background: $SELECTED; }
QPushButton:disabled { color: #BDBBB3; background: transparent; }
QPushButton#primary { background: $ACCENT; color: white; font-weight: 600; }
QPushButton#primary:hover { background: $ACCENT_HOVER; }
QPushButton#flat { background: transparent; color: $MUTED; text-align: left; padding: 7px 10px; }
QPushButton#flat:hover { background: $HOVER; color: $TEXT; }
QPushButton#danger { background: transparent; color: $MUTED; padding: 5px 10px; }
QPushButton#danger:hover { background: #F8E6E0; color: #A8402A; }

#notesList { background: transparent; border: none; outline: none; padding: 0; }

QToolBar { background: transparent; border: none; spacing: 2px; padding: 0; }
QToolButton { background: transparent; border: none; border-radius: 6px; padding: 5px 10px; }
QToolButton:hover { background: $HOVER; }
QToolButton:checked { background: $SELECTED; }
QToolButton:disabled { color: #C9C7BF; }

QPushButton#tagChip { background: $FIELD; color: $TEXT; border-radius: 10px; padding: 3px 9px; }
QPushButton#tagChip:hover { background: #F8E6E0; color: #A8402A; }
QPushButton#addTag { background: transparent; color: $MUTED; padding: 3px 8px; }
QPushButton#addTag:hover { background: $HOVER; color: $TEXT; }
#tagPicker { background: $EDITOR; border: 1px solid $LINE; border-radius: 8px; }
#tagPickerList { background: transparent; border: none; padding: 0; }
#editor { background: $EDITOR; border: none; selection-background-color: #F2D7C9; selection-color: $TEXT; }
#info, #hint { color: $MUTED; }
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
QScrollBar::handle:vertical { background: #D8D6CF; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #C4C2BA; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: $EDITOR; border: 1px solid $LINE; padding: 4px; }
QMenu::item { padding: 6px 22px; border-radius: 5px; }
QMenu::item:selected { background: $HOVER; }
QMenu::separator { height: 1px; background: $LINE; margin: 4px 8px; }
QToolTip { background: $TEXT; color: white; border: none; padding: 4px 8px; }
""").substitute(globals())
