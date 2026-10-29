"""Dialog for renaming, merging and deleting tags."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout)

from .file_store import NoteStore, clean_tag


def plural(n: int) -> str:
    return f"{n} note" if n == 1 else f"{n} notes"


class ManageTagsDialog(QDialog):
    def __init__(self, store: NoteStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.changed = False
        self.setWindowTitle("Manage tags")
        self.resize(360, 420)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self.rename)
        self.list.currentItemChanged.connect(self._update_buttons)

        self.rename_btn = QPushButton("Rename…")
        self.rename_btn.clicked.connect(self.rename)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addWidget(self.rename_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)

        hint = QLabel("Renaming a tag to an existing tag's name merges them.", objectName="hint")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        layout.addWidget(hint)
        layout.addLayout(buttons)
        self.reload()

    def reload(self, select: str | None = None) -> None:
        self.list.clear()
        for name, count in self.store.tag_counts():
            item = QListWidgetItem(f"#{name}  ({plural(count)})")
            item.setData(Qt.ItemDataRole.UserRole, (name, count))
            self.list.addItem(item)
            if select is not None and name.lower() == select.lower():
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._update_buttons()

    def _selected(self) -> tuple[str, int] | None:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_buttons(self, *_) -> None:
        has_tag = self._selected() is not None
        self.rename_btn.setEnabled(has_tag)
        self.delete_btn.setEnabled(has_tag)

    def rename(self, *_) -> None:
        selected = self._selected()
        if selected is None:
            return
        old, _count = selected
        new, ok = QInputDialog.getText(self, "Rename tag", f"New name for #{old}:", text=old)
        new = clean_tag(new)  # one word; spaces become '-'
        if not ok or not new or new == old:
            return
        existing = self.store.find_tag(new)
        if existing is not None and existing.lower() != old.lower():
            answer = QMessageBox.question(
                self, "Merge tags", f"#{existing} already exists. Merge #{old} into it?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            new = existing
        self.store.rename_tag(old, new)
        self.changed = True
        self.reload(select=new)

    def delete(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        name, count = selected
        answer = QMessageBox.question(
            self, "Delete tag",
            f"Remove #{name} from {plural(count)}? The notes themselves are kept.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_tag(name)
        self.changed = True
        self.reload()
