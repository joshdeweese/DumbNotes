"""Notes stored as plain text files: one .md file per note, images in images/.

Each file starts with a small header (front matter) holding the timestamps and tags:

    ---
    created: 2026-10-12T09:41:07
    modified: 2026-10-29T14:03:55
    tags: home, projects
    ---
    Kitchen remodel
    ...
    ![|400](images/3f9c2a71....png)

Every note is read into memory at startup, which keeps listing and searching instant.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile

IMAGE_LINK = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# Earlier versions named files "2026-10-12 Kitchen remodel.md"; these get renamed.
TITLE_NAMED = re.compile(r"^\d{4}-\d{2}-\d{2} .+\.md$")
SYSTEM_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}  # made by Finder / Explorer


def now() -> str:
    """Local time as an ISO string, which also sorts correctly as text."""
    return datetime.now().isoformat(timespec="seconds")


def title_from_text(text: str) -> str:
    """The first non-empty line, ignoring image links."""
    for line in text.splitlines():
        line = IMAGE_LINK.sub("", line).strip()
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


def _split_tags(value: str) -> list[str]:
    seen, tags = set(), []
    for raw in value.split(","):
        tag = raw.strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    return tags


class NoteStore:
    def __init__(self, folder: Path):
        self.folder = folder
        self.images_dir = folder / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self._notes: dict[int, dict] = {}
        self._next_id = 1
        for path in sorted(folder.glob("*.md")):
            self._load(path)
        self._rename_title_named()

    def close(self) -> None:
        pass  # every save is written straight to disk

    # --- files ------------------------------------------------------------

    def _load(self, path: Path) -> None:
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        fields, body = _parse(raw)
        # A file added by hand may have no header; fall back to its file date.
        fallback = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        self._add(path, body, fields.get("created") or fallback,
                  fields.get("modified") or fallback, _split_tags(fields.get("tags", "")))

    def _add(self, path: Path, body: str, created: str, modified: str, tags: list[str]) -> int:
        note_id = self._next_id
        self._next_id += 1
        self._notes[note_id] = {"id": note_id, "path": path, "body": body,
                                "title": title_from_text(body), "created_at": created,
                                "modified_at": modified, "tags": tags}
        return note_id

    def _write(self, note: dict) -> None:
        """Write the note to disk; a new note gets its file name here."""
        header = (f"---\ncreated: {note['created_at']}\nmodified: {note['modified_at']}\n"
                  f"tags: {', '.join(note['tags'])}\n---\n")
        target = note["path"] or self._free_name(self.folder, note["created_at"])
        temp = target.with_name(f".{target.name}.tmp")
        temp.write_text(header + note["body"], encoding="utf-8", newline="\n")
        os.replace(temp, target)  # never leaves a half-written note behind
        note["path"] = target

    @staticmethod
    def _free_name(folder: Path, created: str) -> Path:
        """'2026-10-12.md' for the day's first note, then '2026-10-12-2.md' and so on."""
        day = created[:10]
        candidate, n = folder / f"{day}.md", 2
        while candidate.exists():
            candidate, n = folder / f"{day}-{n}.md", n + 1
        return candidate

    def _rename_title_named(self) -> None:
        old_style = [n for n in self._notes.values() if TITLE_NAMED.match(n["path"].name)]
        for note in sorted(old_style, key=lambda n: n["created_at"]):
            target = self._free_name(self.folder, note["created_at"])
            note["path"].rename(target)
            note["path"] = target

    def move_to(self, dest: Path) -> None:
        """Move every note and image into another folder and keep working from there.

        Notes already in that folder are added to the list. A note whose file name is taken
        gets the next free number for its day. The old folder is removed if nothing else is
        left in it.
        """
        old_folder, old_images = self.folder, self.images_dir
        new_images = dest / "images"
        new_images.mkdir(parents=True, exist_ok=True)
        already_there = sorted(dest.glob("*.md"))
        for image in old_images.iterdir():
            if image.is_file() and not (new_images / image.name).exists():
                shutil.move(str(image), new_images / image.name)
        for note in self._notes.values():
            if note["path"] is None or not note["path"].exists():
                continue
            target = dest / note["path"].name
            if target.exists():
                target = self._free_name(dest, note["created_at"])
            shutil.move(str(note["path"]), target)
            note["path"] = target
        self.folder, self.images_dir = dest, new_images
        for path in already_there:
            self._load(path)
        self._rename_title_named()
        for folder in (old_images, old_folder):
            try:
                leftovers = list(folder.iterdir())
                if all(p.name in SYSTEM_FILES for p in leftovers):
                    for p in leftovers:
                        p.unlink()
                folder.rmdir()  # only succeeds when empty
            except OSError:
                pass

    @staticmethod
    def _trash(path: Path) -> None:
        """Move to the Recycle Bin / Trash, so a deleted note can be recovered."""
        if path.exists() and not QFile.moveToTrash(str(path)):
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
        """Move the note, and any images no other note uses, to the trash."""
        note = self._notes.pop(note_id)
        if note["path"] is not None:
            self._trash(note["path"])
        still_used = {p for other in self._notes.values() for p in image_paths(other["body"])}
        for rel in image_paths(note["body"]):
            if rel not in still_used:
                self._trash(self.folder / rel)

    def list_notes(self, search: str = "", tag: str | None = None) -> list[dict]:
        """Notes matching the search text (title, text or tag) and the tag filter, newest first."""
        search = search.lower()
        tag = tag.lower() if tag else None
        found = []
        for note in self._notes.values():
            tags = [t.lower() for t in note["tags"]]
            if tag is not None and tag not in tags:
                continue
            if search and search not in IMAGE_LINK.sub("", note["body"]).lower() \
                    and not any(search in t for t in tags):
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
