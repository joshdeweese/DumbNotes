"""Notes stored as plain text: each note has its own folder holding its .md file.

    DumbNotes/
      2026-10-12/
        2026-10-12.md      the note
        images/            images pasted into the note
        quote.pdf          anything else you keep with the note (the app ignores these)

Each .md file starts with a small header (front matter) holding the timestamps and tags:

    ---
    created: 2026-10-12T09:41:07
    modified: 2026-10-29T14:03:55
    tags: home, projects
    ---
    Kitchen remodel
    ...
    ![|400](images/3f9c2a71....png)

Image links are relative to the note's folder. Every note is read into memory at startup,
which keeps listing and searching instant.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile

IMAGE_LINK = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# Earlier versions named files "2026-10-12 Kitchen remodel.md"; these get date names.
TITLE_NAMED = re.compile(r"^\d{4}-\d{2}-\d{2} .+\.md$")
SYSTEM_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}  # made by Finder / Explorer


def now() -> str:
    """Local time as an ISO string, which also sorts correctly as text."""
    return datetime.now().isoformat(timespec="seconds")


MARKDOWN_LINK = re.compile(r"\[([^\]\n]+)\]\([^)\s]+\)")
MARKDOWN_MARKS = re.compile(r"^\s*(#{1,6}\s+|>\s?|[-*+]\s+(\[[ xX]\]\s+)?)|\*\*|__|~~|`")


def title_from_text(text: str) -> str:
    """The first non-empty line, without image links or Markdown symbols."""
    for line in text.splitlines():
        line = IMAGE_LINK.sub("", line)
        line = MARKDOWN_MARKS.sub("", MARKDOWN_LINK.sub(r"\1", line)).strip()
        if line:
            return line[:80]
    return ""


def image_paths(text: str) -> list[str]:
    return [m.group(2).strip() for m in IMAGE_LINK.finditer(text)]


def _parse(raw: str) -> tuple[dict[str, str], str]:
    """Split a file into its header fields and the note text."""
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 3)
        if end != -1:
            fields = {}
            for line in raw[4:end].splitlines():
                key, sep, value = line.partition(":")
                if sep:
                    fields[key.strip().lower()] = value.strip()
            return fields, raw[end + 5:]
    return {}, raw


def clean_tag(name: str) -> str:
    """Tags are single words, shown as #word: drop a leading '#', join words with '-'."""
    return "-".join(name.replace(",", " ").strip().lstrip("#").split())


def parse_search(query: str) -> tuple[str, list[str]]:
    """Split a search into free text and #tags: 'oak #home #2026' -> ('oak', ['home', '2026'])."""
    words, tags = [], []
    for word in query.split():
        if word.startswith("#"):
            if clean_tag(word):
                tags.append(clean_tag(word))
        else:
            words.append(word)
    return " ".join(words), tags


def _split_tags(value: str) -> list[str]:
    seen, tags = set(), []
    for raw in value.split(","):
        tag = clean_tag(raw)
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tags


class NoteStore:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self._notes: dict[int, dict] = {}
        self._next_id = 1
        self._load_folder()

    def close(self) -> None:
        pass  # every save is written straight to disk

    # --- files ------------------------------------------------------------

    def _load_folder(self) -> None:
        self._load_paths(sorted(self.folder.iterdir()))

    def _load_paths(self, paths: list[Path]) -> None:
        """Read note folders, and move loose .md files into folders of their own."""
        for path in paths:
            if path.is_dir():
                note_file = self._note_file(path)
                if note_file is not None:
                    self._load(note_file)
            elif path.suffix == ".md" and not path.name.startswith("."):
                self._load(path)
        for note in sorted((n for n in self._notes.values() if n["dir"] is None),
                           key=lambda n: n["created_at"]):
            self._into_folder(note)
        self._remove_if_empty(self.folder / "images")  # the shared folder older versions used

    @staticmethod
    def _note_file(folder: Path) -> Path | None:
        """The note in a note folder: '<folder name>.md', or its only .md file."""
        named = folder / f"{folder.name}.md"
        if named.is_file():
            return named
        found = list(folder.glob("*.md"))
        return found[0] if len(found) == 1 else None

    def _load(self, path: Path) -> None:
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        fields, body = _parse(raw)
        # A file added by hand may have no header; fall back to its file date.
        fallback = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        note_id = self._add(path, body, fields.get("created") or fallback,
                            fields.get("modified") or fallback,
                            _split_tags(fields.get("tags", "")))
        if path.parent != self.folder:
            self._notes[note_id]["dir"] = path.parent

    def _into_folder(self, note: dict) -> None:
        """Move a loose note file (the older layout) into its own folder, with its images."""
        old = note["path"]
        stem = old.stem
        if TITLE_NAMED.match(old.name) or (self.folder / stem).exists():
            stem = self._free_name(self.folder, note["created_at"]).name
        note_dir = self.folder / stem
        (note_dir / "images").mkdir(parents=True)
        for rel in image_paths(note["body"]):
            source = self.folder / rel
            if source.is_file() and source.parent == self.folder / "images":
                shutil.move(str(source), note_dir / "images" / source.name)
        note["dir"], note["path"] = note_dir, note_dir / f"{stem}.md"
        shutil.move(str(old), note["path"])

    def _add(self, path: Path, body: str, created: str, modified: str, tags: list[str]) -> int:
        note_id = self._next_id
        self._next_id += 1
        self._notes[note_id] = {"id": note_id, "dir": None, "path": path, "body": body,
                                "title": title_from_text(body), "created_at": created,
                                "modified_at": modified, "tags": tags}
        return note_id

    def _write(self, note: dict) -> None:
        """Write the note to disk; a new note gets its folder here."""
        if note["path"] is None:
            note["dir"] = self._free_name(self.folder, note["created_at"])
            note["dir"].mkdir(parents=True)
            note["path"] = note["dir"] / f"{note['dir'].name}.md"
        header = (f"---\ncreated: {note['created_at']}\nmodified: {note['modified_at']}\n"
                  f"tags: {', '.join(note['tags'])}\n---\n")
        # Rewrite the file in place (not via a temporary file swapped in), so an edit changes
        # only the .md file's date and the note's folder keeps its own date in Finder.
        with open(note["path"], "w", encoding="utf-8", newline="\n") as f:
            f.write(header + note["body"])
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _free_name(folder: Path, created: str) -> Path:
        """'2026-10-12' for the day's first note, then '2026-10-12-2' and so on."""
        day = created[:10]
        candidate, n = folder / day, 2
        while candidate.exists() or candidate.with_suffix(".md").exists():
            candidate, n = folder / f"{day}-{n}", n + 1
        return candidate

    @staticmethod
    def _remove_if_empty(folder: Path) -> None:
        """Remove a folder if nothing but Finder / Explorer files is left in it."""
        try:
            leftovers = list(folder.iterdir())
            if all(p.name in SYSTEM_FILES for p in leftovers):
                for p in leftovers:
                    p.unlink()
            folder.rmdir()  # only succeeds when empty
        except OSError:
            pass

    def move_to(self, dest: Path) -> None:
        """Move every note folder into another folder and keep working from there.

        Notes already in that folder are added to the list. A note whose folder name is taken
        gets the next free number for its day. The old folder is removed if nothing else is
        left in it.
        """
        old_folder = self.folder
        dest.mkdir(parents=True, exist_ok=True)
        already_there = sorted(dest.iterdir())
        for note in self._notes.values():
            if note["dir"] is None or not note["dir"].exists():
                continue
            target = dest / note["dir"].name
            if target.exists():
                target = self._free_name(dest, note["created_at"])
            shutil.move(str(note["dir"]), target)
            note_file = target / note["path"].name
            if note_file.name != f"{target.name}.md":
                note_file = note_file.rename(target / f"{target.name}.md")
            note["dir"], note["path"] = target, note_file
        self.folder = dest
        self._load_paths(already_there)
        self._remove_if_empty(old_folder / "images")
        self._remove_if_empty(old_folder)

    @staticmethod
    def _trash(path: Path) -> None:
        """Move to the Recycle Bin / Trash, so a deleted note can be recovered."""
        if path.exists() and not QFile.moveToTrash(str(path)):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)

    # --- notes ------------------------------------------------------------

    def create_note(self) -> int:
        ts = now()
        note_id = self._add(None, "", ts, ts, [])
        self._write(self._notes[note_id])
        return note_id

    def import_note(self, body: str, created: str, modified: str, tags: list[str]) -> int:
        note_id = self._add(None, body, created, modified, self._known_spelling(tags))
        self._write(self._notes[note_id])
        return note_id

    def get_note(self, note_id: int) -> dict | None:
        return self._notes.get(note_id)

    def get_tags(self, note_id: int) -> list[str]:
        return sorted(self._notes[note_id]["tags"], key=str.lower)

    def save_note(self, note_id: int, body: str, tags: list[str]) -> str:
        """Save the text and tags, bump the modified time, and return it."""
        note = self._notes[note_id]
        note["body"] = body
        note["title"] = title_from_text(body)
        note["tags"] = self._known_spelling(tags, exclude=note_id)
        note["modified_at"] = now()
        self._write(note)
        return note["modified_at"]

    def delete_note(self, note_id: int) -> None:
        """Move the note's whole folder, attachments included, to the trash."""
        note = self._notes.pop(note_id)
        self._trash(note["dir"] or note["path"])

    def attachment_count(self, note_id: int) -> int:
        """Files in the note's folder, not counting the note itself or its images folder."""
        note = self._notes[note_id]
        if note["dir"] is None or not note["dir"].is_dir():
            return 0
        count = 0
        for root, dirs, files in os.walk(note["dir"]):
            if Path(root) == note["dir"]:
                dirs[:] = [d for d in dirs if d != "images"]
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            count += sum(1 for f in files if not f.startswith(".") and f not in SYSTEM_FILES
                         and Path(root, f) != note["path"])
        return count

    def list_notes(self, text: str = "", tags: list[str] = ()) -> list[dict]:
        """Notes containing the text and having every one of the tags, newest first."""
        text = text.lower()
        wanted = {t.lower() for t in tags}
        found = []
        for note in self._notes.values():
            if not wanted <= {t.lower() for t in note["tags"]}:
                continue
            if text and text not in IMAGE_LINK.sub("", note["body"]).lower():
                continue
            found.append({**note, "tags": ", ".join(self.get_tags(note["id"]))})
        found.sort(key=lambda n: (n["modified_at"], n["id"]), reverse=True)
        return found

    # --- tags -------------------------------------------------------------

    def _known_spelling(self, tags: list[str], exclude: int | None = None) -> list[str]:
        """Use the spelling already in use elsewhere, so 'Work' and 'work' stay one tag."""
        known = {t.lower(): t for n in self._notes.values() if n["id"] != exclude
                 for t in n["tags"]}
        return [known.get(t.lower(), t) for t in _split_tags(",".join(tags))]

    def all_tags(self) -> list[str]:
        return [name for name, _ in self.tag_counts()]

    def tag_counts(self) -> list[tuple[str, int]]:
        counts: dict[str, list] = {}
        for note in self._notes.values():
            for tag in note["tags"]:
                counts.setdefault(tag.lower(), [tag, 0])[1] += 1
        return sorted(((name, n) for name, n in counts.values()), key=lambda c: c[0].lower())

    def find_tag(self, name: str) -> str | None:
        """The stored spelling of a tag, matching case-insensitively."""
        for tag in self.all_tags():
            if tag.lower() == name.lower():
                return tag
        return None

    def rename_tag(self, old: str, new: str) -> None:
        """Rename a tag; if another tag already has the new name, merge into it.

        Only the tags line of each file changes, so the notes keep their modified times.
        """
        new = clean_tag(new)
        existing = self.find_tag(new)
        if existing is not None and existing.lower() != old.lower():
            new = existing
        for note in self._notes.values():
            lowered = [t.lower() for t in note["tags"]]
            if old.lower() in lowered:
                tags = [new if t.lower() == old.lower() else t for t in note["tags"]]
                note["tags"] = _split_tags(",".join(tags))
                self._write(note)

    def delete_tag(self, name: str) -> None:
        """Remove a tag from every note (the notes are kept)."""
        for note in self._notes.values():
            if name.lower() in (t.lower() for t in note["tags"]):
                note["tags"] = [t for t in note["tags"] if t.lower() != name.lower()]
                self._write(note)
