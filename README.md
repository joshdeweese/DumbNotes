# DumbNotes

A simple desktop notes app in Python (PySide6) for Windows (and macOS). Each note is a plain
text file in a folder of its own, where you can also keep any other files that go with it.

- Left pane: every note with the day it was last modified, newest first, grouped by month.
- Search: type words to find in note text, `#tag` to show notes with that tag, or both,
  e.g. `oak #kitchen #2026` (a note has to match everything). Typing `#` suggests existing tags.
- Right pane: plain text editor with live Markdown: every line except the one you're editing is
  shown formatted (headings, **bold**, *italic*, ~~strike~~, `code`, bullets, `- [ ]` checkboxes
  you can click, > quotes, links, --- rules and ``` code blocks). The file stays plain Markdown.
  Cmd+click (Ctrl+click on Windows) opens a link. The first line is the title and is shown larger.
- The Markdown button (M↓) at the bottom of the note list opens a panel of examples; click one to
  add it to your note at the cursor (or around the selected text).
- Bullets: start a line with `- `; Enter continues the list, Tab / Shift+Tab nest it, Enter on an empty bullet ends it.
- Paste images straight from the clipboard (e.g. Snipping Tool), or drop image files in. Drag an image's corner to resize it.
- Tags: one word each, written `#tag` (spaces become `-`). They sit at the bottom right of a note;
  **+ Add Tag** picks an existing tag or creates a new one, and clicking a tag removes it.
  **Options → Manage Tags…** renames, merges or deletes tags across all notes.
- **Options → Dark Mode** (Cmd/Ctrl+Shift+D) switches between the light and dark look; the app remembers it.
- Notes autosave as you type. Hover over a note in the list to see when it was created and last modified.
- The folder button under the editor opens the note's folder in Finder / File Explorer. Its number is
  how many other files are in there (not counting the note itself or its pasted images).
- Ctrl+N makes a new note; Delete in the list removes one.
- **Options → Check for Updates…** gets the latest version from GitHub and restarts the app.

The note title is the first line of the note.

## Run

```
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```

### macOS app

`python main.py` shows up in the Dock as "Python". To get a proper DumbNotes app with its own
name and icon in the Dock, Finder, Spotlight and Launchpad, run once:

```
.venv/bin/python make_mac_app.py
```

This builds `~/Applications/DumbNotes.app`, which runs `main.py` from this folder, so code changes
show up the next time you open it. Run it again if you move the project folder or Homebrew
upgrades Python.

## Install on another computer

Each computer runs its own copy of the code, cloned from GitHub, so it can update itself.
You need [git](https://git-scm.com) and Python 3.10 or newer. The repository is private, so
git asks you to sign in to GitHub the first time (Git for Windows opens a browser window for it).

Windows:

```
git clone https://github.com/joshdeweese/DumbNotes.git
cd DumbNotes
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

To start it without a console window, make a shortcut (right-click the desktop → New →
Shortcut) to `<the DumbNotes folder>\.venv\Scripts\pythonw.exe main.py`, set its *Start in*
to the DumbNotes folder and its icon to `notes_app\icon.ico`. Pin it to the taskbar if you like.

macOS:

```
git clone https://github.com/joshdeweese/DumbNotes.git
cd DumbNotes
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python make_mac_app.py
```

## Updating

Push changes to `main` on GitHub. Then on each computer choose **Options → Check for
Updates…**: it lists what's new and, if you say yes, pulls it, installs any new requirements
and restarts DumbNotes. Notes aren't affected; they live in the notes folder, not with the code.
(From a terminal, `git pull` in the DumbNotes folder does the same; restart the app afterwards.)

If the update stops with "Your local changes … would be overwritten", that copy has edited
files of its own: commit or discard them (`git status` shows which) and try again.

## Where notes are stored

Notes live in `Documents/DumbNotes`. Each note has its own folder, named by the day it was
created (`2026-10-29`, then `2026-10-29-2` for the day's second note, and so on):

```
DumbNotes/
  2026-10-29/
    2026-10-29.md      the note
    images/            images pasted into the note
    quote.pdf          anything else you keep with the note (the app doesn't show these)
```

Each `.md` file starts with a small header:

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

`![|400](images/...)` is an image shown 400 px wide, relative to the note's folder. Deleting a note
sends its whole folder, attachments included, to the Recycle Bin / Trash.

To keep notes somewhere else (e.g. OneDrive or Dropbox), choose **Options → Notes Folder…**
and pick a folder: every note folder is moved there and the app remembers it.
The `NOTES_APP_DATA` environment variable, if set, overrides this.
Notes from older versions are converted on first start: loose `.md` files are moved into
folders of their own (with their images), and notes from the database version (`notes.db`) are
moved into files, with the database kept as `notes.db.migrated`.

## Build a Windows .exe (optional, run on Windows)

```
pip install pyinstaller
pyinstaller --windowed --name DumbNotes --icon notes_app/icon.ico --add-data "notes_app/*.svg;notes_app" main.py
```

The app ends up in `dist\DumbNotes\`.
