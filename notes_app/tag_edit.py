"""Comma-separated tag field that autocompletes from existing tags."""

from PySide6.QtCore import QEvent, QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLineEdit


class TagEdit(QLineEdit):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._all_tags: list[str] = []
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)
        self.textEdited.connect(lambda: self._show_completions())

    def set_tags(self, tags: list[str]) -> None:
        self._all_tags = tags

    def _current_segment(self) -> tuple[int, int]:
        """Start and end of the tag the cursor is in."""
        text, pos = self.text(), self.cursorPosition()
        start = text.rfind(",", 0, pos) + 1
        end = text.find(",", pos)
        return start, len(text) if end < 0 else end

    def _show_completions(self, show_all: bool = False) -> None:
        text = self.text()
        start, end = self._current_segment()
        prefix = text[start:self.cursorPosition()].strip()
        others = (text[:start] + text[end:]).split(",")
        used = {t.strip().lower() for t in others if t.strip()}
        self._model.setStringList([t for t in self._all_tags if t.lower() not in used])

        popup = self._completer.popup()
        self._completer.setCompletionPrefix(prefix)
        count = self._completer.completionCount()
        exact = count == 1 and self._completer.currentCompletion().lower() == prefix.lower()
        if (not prefix and not show_all) or count == 0 or exact:
            popup.hide()
            return
        self._completer.complete()
        # Highlight the top match so Enter or Tab picks it straight away.
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))

    def _insert_completion(self, tag: str) -> None:
        text = self.text()
        start, end = self._current_segment()
        before = text[:start].rstrip()
        before = f"{before} " if before else ""
        after = text[end + 1:].strip() if end < len(text) else ""
        new_before = f"{before}{tag}, "
        self.setText(new_before + after)
        self.setCursorPosition(len(new_before))

    def event(self, event):
        # Tab normally moves focus before keyPressEvent sees it; use it to accept instead.
        if event.type() != QEvent.Type.KeyPress or not hasattr(self, "_completer"):
            return super().event(event)
        popup = self._completer.popup()
        if (event.key() == Qt.Key.Key_Tab
                and popup.isVisible() and popup.currentIndex().isValid()):
            tag = popup.currentIndex().data()
            popup.hide()
            self._insert_completion(tag)
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        popup = self._completer.popup()
        if not popup.isVisible() and event.key() == Qt.Key.Key_Down:
            self._show_completions(show_all=True)  # Down arrow lists every tag
            return
        super().keyPressEvent(event)
