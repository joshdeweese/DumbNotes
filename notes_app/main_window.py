"""Main window: note list on the left, editor on the right."""

import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QFileDialog, QMessageBox, QPushButton, QSplitter, QVBoxLayout,
                               QWidget)

from .editor import NoteEditor
from .file_store import NoteStore, title_from_text
from .notes_list import HEADER_ROLE, ID_ROLE, NOTE_ROLE, NoteDelegate, month_label
from .tag_dialog import ManageTagsDialog
from .tag_edit import TagEdit

ALL_TAGS = "All tags"
FOLDER_ICON = Path(__file__).with_name("folder.svg")
FILE_MANAGER = {"darwin": "Finder", "win32": "File Explorer"}.get(sys.platform, "file manager")
AUTOSAVE_MS = 800
FOLDER_SETTING = "notes_folder"


def settings() -> QSettings:
    return QSettings("DumbNotes", "DumbNotes")


def fmt_ts(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")


def parse_tags(text: str) -> tuple[str, ...]:
    seen, tags = set(), []
    for raw in text.split(","):
        tag = raw.strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tuple(tags)


class MainWindow(QMainWindow):
    def __init__(self, store: NoteStore):
        super().__init__()
        self.store = store
        self.current_id: int | None = None
        self.saved_state: tuple[str, tuple[str, ...]] | None = None

        self.setWindowTitle("DumbNotes")
        self.resize(1150, 740)

        splitter = QSplitter()
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_list_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 830])
        self.setCentralWidget(splitter)

        self.save_timer = QTimer(self, singleShot=True, interval=AUTOSAVE_MS)
        self.save_timer.timeout.connect(self.save_current)

        new_action = QAction("New note", self, shortcut=QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.new_note)
        self.addAction(new_action)

        self.refresh_tag_filter()
        self.refresh_list()
        self._set_editing_enabled(False)
        self._select_first_note()

    # --- layout -----------------------------------------------------------

    def _build_list_pane(self) -> QWidget:
        new_btn = QPushButton("+  New note", objectName="primary")
        new_btn.clicked.connect(self.new_note)

        self.search = QLineEdit(placeholderText="Search notes", clearButtonEnabled=True)
        self.search.textChanged.connect(lambda: self.refresh_list())

        self.tag_filter = QComboBox()
        self.tag_filter.currentIndexChanged.connect(lambda: self.refresh_list())

        self.notes_list = QListWidget(objectName="notesList")
        self.notes_list.setItemDelegate(NoteDelegate(self.notes_list))
        self.notes_list.setMouseTracking(True)
        self.notes_list.setFrameShape(QFrame.Shape.NoFrame)
        self.notes_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.notes_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes_list.itemSelectionChanged.connect(self.on_selection_changed)
        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self.notes_list)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self.delete_note)

        manage_btn = QPushButton("Manage tags…", objectName="flat")
        manage_btn.clicked.connect(self.manage_tags)
        self.folder_btn = QPushButton("Notes folder…", objectName="flat")
        self.folder_btn.clicked.connect(self.choose_folder)
        self._update_folder_tooltip()
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)
        bottom_row.addWidget(manage_btn)
        bottom_row.addWidget(self.folder_btn)

        pane = QWidget(objectName="sidebar")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        pane.setMinimumWidth(240)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 14, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(new_btn)
        layout.addSpacing(4)
        layout.addWidget(self.search)
        layout.addWidget(self.tag_filter)
        layout.addSpacing(2)
        layout.addWidget(self.notes_list, 1)
        layout.addLayout(bottom_row)
        return pane

    def _build_editor_pane(self) -> QWidget:
        self.editor = NoteEditor()
        self.editor.setObjectName("editor")
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.textChanged.connect(self.schedule_save)

        self.tags_edit = TagEdit(objectName="tagsEdit",
                                 placeholderText="Add tags, separated by commas  (↓ for existing)")
        self.tags_edit.textChanged.connect(self.schedule_save)

        self.delete_btn = QPushButton("Delete", objectName="danger")
        self.delete_btn.clicked.connect(self.delete_note)
        top_row = QHBoxLayout()
        top_row.addStretch(1)
        top_row.addWidget(self.delete_btn)

        self.info = QLabel(objectName="info")

        header = QVBoxLayout()
        header.setContentsMargins(20, 12, 20, 0)
        header.setSpacing(6)
        header.addLayout(top_row)
        header.addWidget(self.tags_edit)

        # Opens the note's own folder, where you can keep other files that go with it.
        self.attach_btn = QPushButton(objectName="attachBtn", icon=QIcon(str(FOLDER_ICON)))
        self.attach_btn.setIconSize(QSize(16, 16))
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.clicked.connect(self.open_note_folder)
        self.folder_watcher = QFileSystemWatcher(self)
        self.folder_watcher.directoryChanged.connect(lambda _: self.update_attachments())

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 6, 24, 10)
        footer.setSpacing(10)
        footer.addWidget(self.attach_btn)
        footer.addWidget(self.info)
        footer.addStretch(1)

        pane = QWidget(objectName="editorPane")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.editor, 1)
        layout.addLayout(footer)
        return pane

    def _set_editing_enabled(self, enabled: bool) -> None:
        for widget in (self.editor, self.tags_edit, self.delete_btn):
            widget.setEnabled(enabled)
        self.attach_btn.setVisible(enabled)

    # --- list -------------------------------------------------------------

    def refresh_tag_filter(self) -> None:
        current = self.tag_filter.currentText()
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem(ALL_TAGS)
        tags = self.store.all_tags()
        self.tag_filter.addItems(tags)
        self.tags_edit.set_tags(tags)
        index = self.tag_filter.findText(current)
        self.tag_filter.setCurrentIndex(max(index, 0))
        self.tag_filter.blockSignals(False)
        if index < 0 and current not in ("", ALL_TAGS):
            self.refresh_list()

    def refresh_list(self) -> None:
        tag = self.tag_filter.currentText()
        notes = self.store.list_notes(self.search.text().strip(),
                                      None if tag in ("", ALL_TAGS) else tag)
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        month = None
        for note in notes:  # newest first, so each month's heading comes before its notes
            if month_label(note["modified_at"]) != month:
                month = month_label(note["modified_at"])
                header = QListWidgetItem()
                header.setData(HEADER_ROLE, month)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.notes_list.addItem(header)
            item = QListWidgetItem()
            item.setData(ID_ROLE, note["id"])
            self._set_item_note(item, note["title"], note["tags"], note["modified_at"],
                                note["created_at"])
            self.notes_list.addItem(item)
        self.notes_list.blockSignals(False)
        item = self._item_for(self.current_id)
        if item is not None:
            self.notes_list.setCurrentItem(item)

    @staticmethod
    def _set_item_note(item: QListWidgetItem, title: str, tags: str, modified: str,
                       created: str) -> None:
        item.setData(NOTE_ROLE, {"title": title, "tags": tags, "modified_at": modified})
        item.setToolTip(f"Created {fmt_ts(created)}\nModified {fmt_ts(modified)}")

    def _first_note_item(self) -> QListWidgetItem | None:
        for row in range(self.notes_list.count()):
            item = self.notes_list.item(row)
            if item.data(ID_ROLE) is not None:
                return item
        return None

    def _select_first_note(self) -> None:
        item = self._first_note_item()
        if item is not None:
            self.notes_list.setCurrentItem(item)

    def _item_for(self, note_id: int | None) -> QListWidgetItem | None:
        if note_id is None:
            return None
        for row in range(self.notes_list.count()):
            item = self.notes_list.item(row)
            if item.data(ID_ROLE) == note_id:
                return item
        return None

    def on_selection_changed(self) -> None:
        items = self.notes_list.selectedItems()
        if not items:
            return
        note_id = items[0].data(ID_ROLE)
        if note_id != self.current_id:
            self.save_current()  # may re-sort the list, moving the selection
            self.load_note(note_id)
            item = self._item_for(note_id)
            if item is not None and self.notes_list.currentItem() is not item:
                self.notes_list.blockSignals(True)
                self.notes_list.setCurrentItem(item)
                self.notes_list.blockSignals(False)

    # --- notes ------------------------------------------------------------

    def load_note(self, note_id: int) -> None:
        note = self.store.get_note(note_id)
        self.current_id = note_id
        self.editor.blockSignals(True)
        self.tags_edit.blockSignals(True)
        self.editor.set_text(note["body"], note["dir"])
        self.tags_edit.setText(", ".join(self.store.get_tags(note_id)))
        self.editor.blockSignals(False)
        self.tags_edit.blockSignals(False)
        self.saved_state = self._editor_state()
        self._set_editing_enabled(True)
        self._show_info(note["created_at"], note["modified_at"])
        self.update_attachments()

    def update_attachments(self) -> None:
        """Show how many files sit in the note's folder, and watch it for changes."""
        if self.folder_watcher.directories():
            self.folder_watcher.removePaths(self.folder_watcher.directories())
        if self.current_id is None:
            return
        note = self.store.get_note(self.current_id)
        if note is None or note["dir"] is None:
            return
        self.folder_watcher.addPath(str(note["dir"]))
        count = self.store.attachment_count(self.current_id)
        self.attach_btn.setText(str(count))
        files = f"{count} file{'s' * (count != 1)}" if count else "No files"
        self.attach_btn.setToolTip(f"{files} kept with this note (not counting images)\n"
                                   f"Click to open its folder in {FILE_MANAGER}")

    def open_note_folder(self) -> None:
        if self.current_id is None:
            return
        self.save_current()  # make sure a brand new note's folder exists
        note_dir = self.store.get_note(self.current_id)["dir"]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(note_dir)))

    def changeEvent(self, event) -> None:
        # Coming back from Finder: pick up files added or removed there.
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.update_attachments()
        super().changeEvent(event)

    def _editor_state(self) -> tuple[str, tuple[str, ...]]:
        return self.editor.text(), parse_tags(self.tags_edit.text())

    def _show_info(self, created: str, modified: str) -> None:
        self.info.setText(f"Created {fmt_ts(created)}     ·     Modified {fmt_ts(modified)}")

    def schedule_save(self) -> None:
        if self.current_id is not None:
            self.save_timer.start()

    def save_current(self) -> None:
        self.save_timer.stop()
        if self.current_id is None:
            return
        text, tags = self._editor_state()
        if (text, tags) == self.saved_state:
            return
        modified = self.store.save_note(self.current_id, text, list(tags))
        tags_changed = self.saved_state is None or tags != self.saved_state[1]
        self.saved_state = (text, tags)

        note = self.store.get_note(self.current_id)
        title = note["title"]
        self._show_info(note["created_at"], modified)
        item = self._item_for(self.current_id)
        if tags_changed:
            self.refresh_tag_filter()
        if item is not None and item is self._first_note_item():
            self._set_item_note(item, title, ", ".join(self.store.get_tags(self.current_id)),
                                modified, note["created_at"])
        else:
            self.refresh_list()  # most recently modified goes to the top
            self.notes_list.scrollToTop()

    def new_note(self) -> None:
        self.save_current()
        note_id = self.store.create_note()
        tag = self.tag_filter.currentText()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.load_note(note_id)
        if tag != ALL_TAGS:
            self.tags_edit.setText(tag)  # new note joins the tag being viewed
            self.save_current()
        self.refresh_list()
        self.editor.setFocus()

    def delete_note(self) -> None:
        if self.current_id is None:
            return
        title = title_from_text(self.editor.text()) or "Untitled"
        count = self.store.attachment_count(self.current_id)
        extra = f" and the {count} other file{'s' * (count != 1)} in its folder" if count else ""
        answer = QMessageBox.question(self, "Delete note", f'Delete "{title}"{extra}?\n\n'
                                      "It goes to the Trash, so you can get it back.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.save_timer.stop()
        self.store.delete_note(self.current_id)
        self.current_id = None
        self.saved_state = None
        self.editor.blockSignals(True)
        self.tags_edit.blockSignals(True)
        self.editor.clear()
        self.tags_edit.clear()
        self.editor.blockSignals(False)
        self.tags_edit.blockSignals(False)
        self.info.clear()
        self.update_attachments()
        self._set_editing_enabled(False)
        self.refresh_tag_filter()
        self.refresh_list()
        self._select_first_note()

    def _update_folder_tooltip(self) -> None:
        self.folder_btn.setToolTip(f"Notes are saved in\n{self.store.folder}\n\n"
                                   "Click to choose another folder")

    def choose_folder(self) -> None:
        """Pick a new notes folder and move every note and image into it."""
        old = self.store.folder
        if os.environ.get("NOTES_APP_DATA"):
            QMessageBox.information(self, "Notes folder",
                                    "The folder is set by the NOTES_APP_DATA environment variable."
                                    " Remove it to choose a folder here.")
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose where to save notes", str(old))
        if not chosen:
            return
        dest = Path(chosen)
        if dest.resolve() == old.resolve():
            return
        if dest.resolve().is_relative_to(old.resolve()):
            QMessageBox.warning(self, "Notes folder",
                                "Choose a folder outside the current notes folder.")
            return
        count = len(self.store.list_notes())
        waiting = sum(1 for p in dest.iterdir()
                      if (p.is_dir() and NoteStore._note_file(p)) or p.suffix == ".md")
        message = (f"Move your {count} note{'s' * (count != 1)} to\n{dest}?\n\n"
                   "Each note's folder moves with everything in it.")
        if waiting:
            message += (f"\n\nThat folder already has {waiting} note"
                        f"{'s' * (waiting != 1)}; they'll be added to your list.")
        answer = QMessageBox.question(self, "Move notes", message)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.save_current()
        try:
            self.store.move_to(dest)
        except OSError as error:
            QMessageBox.warning(self, "Notes folder",
                                f"Some files couldn't be moved:\n{error}\n\n"
                                f"Your notes are still saved in\n{old}")
            return
        settings().setValue(FOLDER_SETTING, str(dest))
        if self.current_id is not None:
            self.editor.note_dir = self.store.get_note(self.current_id)["dir"]
        self.update_attachments()
        self._update_folder_tooltip()
        self.refresh_tag_filter()
        self.refresh_list()

    def manage_tags(self) -> None:
        self.save_current()
        dialog = ManageTagsDialog(self.store, self)
        dialog.exec()
        if not dialog.changed:
            return
        if self.current_id is not None:
            # Show the current note's renamed/removed tags without counting it as an edit.
            self.tags_edit.blockSignals(True)
            self.tags_edit.setText(", ".join(self.store.get_tags(self.current_id)))
            self.tags_edit.blockSignals(False)
            self.saved_state = self._editor_state()
        self.refresh_tag_filter()
        self.refresh_list()

    def closeEvent(self, event) -> None:
        self.save_current()
        self.store.close()
        super().closeEvent(event)
