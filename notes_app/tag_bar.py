"""Tag widgets: the note's #tags with an Add Tag picker, and a search box that suggests #tags."""

import re

from PySide6.QtCore import QPoint, QStringListModel, Qt, Signal
from PySide6.QtWidgets import (QCompleter, QFrame, QHBoxLayout, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from .file_store import clean_tag

CREATE_ROLE = Qt.ItemDataRole.UserRole + 10  # marks the "Create #name" row
PICKER_ROWS = 8


class TagPicker(QFrame):
    """Popup listing existing tags to choose from, with a box to filter or name a new tag."""

    chosen = Signal(str)

    def __init__(self, tags: list[str], parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("tagPicker")
        self.tags = tags
        self.search = QLineEdit(placeholderText="Find or create a tag")
        self.search.textChanged.connect(self._fill)
        self.search.returnPressed.connect(self._choose_current)
        self.search.installEventFilter(self)
        self.list = QListWidget(objectName="tagPickerList")
        self.list.itemClicked.connect(self._choose)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self.setFixedWidth(240)
        self._fill()

    def _fill(self) -> None:
        typed = clean_tag(self.search.text())
        self.list.clear()
        # Existing tags first (so Enter picks a match), then the option to create a new one.
        matches = [t for t in self.tags if typed.lower() in t.lower()]
        matches.sort(key=lambda t: (not t.lower().startswith(typed.lower()), t.lower()))
        for tag in matches:
            item = QListWidgetItem(f"#{tag}")
            item.setData(CREATE_ROLE, tag)
            self.list.addItem(item)
        if typed and typed.lower() not in (t.lower() for t in self.tags):
            item = QListWidgetItem(f"Create #{typed}")
            item.setData(CREATE_ROLE, typed)
            self.list.addItem(item)
        if not self.list.count():
            item = QListWidgetItem("Type a name to create a tag")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        rows = min(self.list.count(), PICKER_ROWS)
        self.list.setFixedHeight(rows * self.list.sizeHintForRow(0) + 6)
        self.adjustSize()

    def eventFilter(self, obj, event):
        # Up / Down in the box move through the list.
        if obj is self.search and event.type() == event.Type.KeyPress \
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            row = max(0, min(self.list.count() - 1, self.list.currentRow() + step))
            self.list.setCurrentRow(row)
            return True
        return super().eventFilter(obj, event)

    def _choose_current(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self._choose(item)

    def _choose(self, item: QListWidgetItem) -> None:
        tag = item.data(CREATE_ROLE)
        if tag:
            self.close()
            self.chosen.emit(tag)

    def show_above(self, widget: QWidget) -> None:
        """Open just above the widget (the Add Tag button sits at the bottom of the window)."""
        self.adjustSize()
        corner = widget.mapToGlobal(QPoint(widget.width(), 0))
        self.move(corner.x() - self.width(), corner.y() - self.height() - 4)
        self.show()
        self.search.setFocus()


class TagBar(QWidget):
    """The open note's tags as #chips (click one to remove it) and an Add Tag button."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self._known: list[str] = []
        self._chips: list[QPushButton] = []
        self.add_btn = QPushButton("+ Add Tag", objectName="addTag")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.open_picker)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)
        self.layout_.addWidget(self.add_btn)

    def set_known(self, tags: list[str]) -> None:
        """All tags in use, offered by the picker."""
        self._known = tags

    def tags(self) -> list[str]:
        return list(self._tags)

    def set_tags(self, tags: list[str]) -> None:
        """Show a note's tags (doesn't count as a change)."""
        self._tags = sorted(tags, key=str.lower)
        self._rebuild()

    def add_tag(self, tag: str) -> None:
        tag = clean_tag(tag)
        if tag and tag.lower() not in (t.lower() for t in self._tags):
            self.set_tags(self._tags + [tag])
            self.changed.emit()

    def remove_tag(self, tag: str) -> None:
        self.set_tags([t for t in self._tags if t != tag])
        self.changed.emit()

    def open_picker(self) -> None:
        on_note = {t.lower() for t in self._tags}
        picker = TagPicker([t for t in self._known if t.lower() not in on_note], self)
        picker.chosen.connect(self.add_tag)
        picker.show_above(self.add_btn)

    def _rebuild(self) -> None:
        for chip in self._chips:
            self.layout_.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
        self._chips = []
        for i, tag in enumerate(self._tags):
            chip = QPushButton(f"#{tag}  ×", objectName="tagChip", toolTip=f"Remove #{tag}")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, t=tag: self.remove_tag(t))
            chip.setEnabled(self.isEnabled())
            self.layout_.insertWidget(i, chip)
            self._chips.append(chip)


class SearchEdit(QLineEdit):
    """Search box: free text, #tags, or both. Suggests existing tags after a '#'."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_tag)
        self.textEdited.connect(lambda: self._suggest())

    def set_tags(self, tags: list[str]) -> None:
        self._model.setStringList([f"#{t}" for t in tags])

    def _tag_being_typed(self) -> re.Match | None:
        return re.search(r"#\S*$", self.text()[:self.cursorPosition()])

    def _suggest(self) -> None:
        match = self._tag_being_typed()
        if match is None:
            self._completer.popup().hide()
            return
        self._completer.setCompletionPrefix(match.group())
        if self._completer.completionCount():
            self._completer.complete()
            # Highlight the first match so Enter picks it.
            self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))
        else:
            self._completer.popup().hide()

    def _insert_tag(self, tag: str) -> None:
        match = self._tag_being_typed()
        if match is None:
            return
        text, pos = self.text(), self.cursorPosition()
        rest = text[pos:].lstrip()
        new = text[:match.start()] + tag + " " + rest
        self.setText(new)
        self.setCursorPosition(match.start() + len(tag) + 1)
