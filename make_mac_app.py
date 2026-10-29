"""Build ~/Applications/DumbNotes.app so the Dock, Finder and Spotlight call the app DumbNotes.

Run with the project's Python:  .venv/bin/python make_mac_app.py

macOS names a running app after the .app bundle it was started from. `python main.py` starts
from Python.app, so the Dock shows "Python". This makes a small bundle of our own that runs
main.py from this project folder with its .venv, using a copy of Python's own launcher.
The code isn't copied, so edits to the project show up the next time the app is opened.

Run it again after moving the project folder or after Homebrew upgrades Python.
"""

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PROJECT = Path(__file__).resolve().parent
TARGET = Path.home() / "Applications" / "DumbNotes.app"
LAUNCHER = Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"

START_SCRIPT = """#!/bin/sh
# Runs DumbNotes from the project folder with its .venv (made by make_mac_app.py).
PROJECT="{project}"
cd "$PROJECT" || exit 1
PYTHONEXECUTABLE="$PROJECT/.venv/bin/python" exec "$(dirname "$0")/python" "$PROJECT/main.py" "$@"
"""


def make_icns(dest: Path) -> None:
    """Render notes_app/icon.svg at every size macOS wants and pack it as an .icns file."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(PROJECT / "notes_app" / "icon.svg"))
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "DumbNotes.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                image = QImage(size * scale, size * scale, QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                renderer.render(painter)
                painter.end()
                suffix = "@2x" if scale == 2 else ""
                image.save(str(iconset / f"icon_{size}x{size}{suffix}.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest)], check=True)
    del app


def main() -> None:
    if sys.platform != "darwin":
        sys.exit("This builds a macOS app; on Windows use the PyInstaller command in README.md.")
    if not LAUNCHER.is_file():
        sys.exit(f"Couldn't find Python's app launcher at {LAUNCHER}")
    if not (PROJECT / ".venv" / "bin" / "python").exists():
        sys.exit("Create the project's .venv first (see README.md).")

    if TARGET.exists():
        shutil.rmtree(TARGET)
    contents = TARGET / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()

    shutil.copy2(LAUNCHER, contents / "MacOS" / "python")
    start = contents / "MacOS" / "DumbNotes"
    start.write_text(START_SCRIPT.format(project=PROJECT))
    start.chmod(0o755)
    make_icns(contents / "Resources" / "DumbNotes.icns")
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump({
            "CFBundleName": "DumbNotes",
            "CFBundleDisplayName": "DumbNotes",
            "CFBundleIdentifier": "com.joshdeweese.dumbnotes",
            "CFBundleExecutable": "DumbNotes",
            "CFBundleIconFile": "DumbNotes",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "1.0",
            "NSHighResolutionCapable": True,
        }, f)

    subprocess.run(["codesign", "--force", "--sign", "-", str(TARGET)], check=True,
                   capture_output=True)
    # Tell Finder / the Dock about the new bundle so they pick up the name and icon.
    lsregister = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
                  "LaunchServices.framework/Support/lsregister")
    if os.path.exists(lsregister):
        subprocess.run([lsregister, "-f", str(TARGET)], check=False)
    print(f"Built {TARGET}")


if __name__ == "__main__":
    main()
