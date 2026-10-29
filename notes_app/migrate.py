"""One-time move of notes from the old notes.db into plain text files."""

import re
import shutil
import sqlite3
from pathlib import Path

from PySide6.QtGui import QTextDocument

from .editor import document_to_text
from .file_store import NoteStore

IMG_SRC = re.compile(r'(<img[^>]+src=")([^"]+)(")')


def migrate_database(db_path: Path, old_images: Path, store: NoteStore) -> int:
    """Copy every note and its images into the store, then rename the database.

    Bold and font sizes are dropped; bullets become '- ' lines. The database is kept as
    notes.db.migrated rather than deleted. Returns how many notes were moved.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    notes = conn.execute("SELECT * FROM notes ORDER BY created_at").fetchall()
    for note in notes:
        tags = [r[0] for r in conn.execute(
            """SELECT t.name FROM tags t JOIN note_tags nt ON nt.tag_id = t.id
               WHERE nt.note_id = ? ORDER BY t.name""", (note["id"],))]
        html = note["body_html"]
        html = IMG_SRC.sub(lambda m: f"{m[1]}images/{m[2]}{m[3]}", html)
        doc = QTextDocument()
        doc.setHtml(html)
        body = document_to_text(doc).replace(" ", " ")
        note_id = store.import_note(body, note["created_at"], note["modified_at"], tags)
        images_dir = store.get_note(note_id)["dir"] / "images"
        for name in IMG_SRC.findall(note["body_html"]):
            source = old_images / name[1]
            if source.is_file():
                images_dir.mkdir(exist_ok=True)
                shutil.copy2(source, images_dir / name[1])
    conn.close()
    db_path.rename(db_path.with_name(db_path.name + ".migrated"))
    return len(notes)
