# DumbNotes

A simple desktop notes app in Python (PySide6) for Windows (and macOS). Each note is a plain
text file.

- Left pane: every note with its tags and modified time, newest first, grouped by month. Search box and tag filter.
- Right pane: plain text editor. The first line is the title and is shown larger.
- Bullets: start a line with `- `; Enter continues the list, Tab / Shift+Tab nest it, Enter on an empty bullet ends it.
- Paste images straight from the clipboard (e.g. Snipping Tool), or drop image files in. Drag an image's corner to resize it.
- Tags: comma separated in the field above the editor.
- Notes autosave as you type. Created and modified times are shown under the editor.
- Ctrl+N makes a new note; Delete in the list removes one.

The note title is the first line of the note.

## Run

```
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```

## Where notes are stored

Notes live in `Documents/DumbNotes`, one `.md` file per note named by the day it was created
(`2026-10-29.md`, then `2026-10-29-2.md` for the day's second note, and so on), with
pasted images in `Documents/DumbNotes/images`. Each file starts with a small header:

```
---
created: 2026-10-12T09:41:07
modified: 2026-10-29T14:03:55
tags: home, projects
---
Kitchen remodel

- Cabinets
  - Oak: $8,200

![|400](images/3f9c2a71....png)
```

`![|400](images/...)` is an image shown 400 px wide. Deleted notes go to the Recycle Bin / Trash.

To keep notes somewhere else (e.g. OneDrive or Dropbox), click **Notes folder…** at the bottom of
the sidebar and pick a folder: every note and image is moved there and the app remembers it.
The `NOTES_APP_DATA` environment variable, if set, overrides this.
Notes from the older database version (`notes.db`) are moved into files on first start, and
the database is kept as `notes.db.migrated`.

## Build a Windows .exe (optional, run on Windows)

```
pip install pyinstaller
pyinstaller --windowed --name DumbNotes --icon notes_app/icon.ico --add-data "notes_app/*.svg;notes_app" main.py
```

The app ends up in `dist\DumbNotes\`.
