"""Entry point: python main.py"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from notes_app.file_store import NoteStore
from notes_app.main_window import FOLDER_SETTING, THEME_SETTING, MainWindow, settings
from notes_app.migrate import migrate_database
from notes_app.style import apply_theme


def notes_dir() -> Path:
    """Where the note files live: NOTES_APP_DATA if set, else the folder chosen in the app,
    else Documents/DumbNotes."""
    override = os.environ.get("NOTES_APP_DATA") or settings().value(FOLDER_SETTING)
    if override:
        return Path(override)
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(documents) / "DumbNotes"


def old_data_dir() -> Path:
    """Where earlier versions kept notes.db: %APPDATA%\\NotesApp, or NOTES_APP_DATA."""
    override = os.environ.get("NOTES_APP_DATA")
    if override:
        return Path(override)
    app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(app_data).parent / "NotesApp"  # the app's name before it became DumbNotes


def open_store() -> NoteStore | None:
    """Open the notes folder. If it can't be created or read (e.g. Documents is a broken link),
    say so and ask for another folder, which is remembered; None if the user gives up."""
    folder = notes_dir()
    while True:
        try:
            return NoteStore(folder)
        except OSError as e:
            QMessageBox.warning(None, "Notes folder", "DumbNotes can't keep its notes in\n"
                                f"{folder}\n\n({e})\n\nChoose another folder for your notes.")
            chosen = QFileDialog.getExistingDirectory(None, "Choose where to save notes",
                                                      str(Path.home()))
            if not chosen:
                return None
            folder = Path(chosen)
            settings().setValue(FOLDER_SETTING, chosen)


ICON = Path(__file__).parent / "notes_app" / "icon.svg"
APP_TITLE = "DumbNotes"


def set_mac_app_name(name: str) -> None:
    """Show our name in the macOS menu bar instead of "python" when run from source.

    The menu bar uses CFBundleName from the running program's bundle, so we patch it
    in the Objective-C runtime before Qt starts the Cocoa application.
    """
    import ctypes
    import ctypes.util
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

        def send(obj, selector, *args):
            proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                     *[ctypes.c_void_p] * len(args))
            msg = ctypes.cast(objc.objc_msgSend, proto)
            return msg(obj, objc.sel_registerName(selector), *args)

        def nsstring(text):
            return cf.CFStringCreateWithCString(None, text.encode(), 0x08000100)  # UTF-8

        bundle = send(objc.objc_getClass(b"NSBundle"), b"mainBundle")
        info = send(bundle, b"localizedInfoDictionary") or send(bundle, b"infoDictionary")
        if info:
            send(info, b"setObject:forKey:", nsstring(name), nsstring("CFBundleName"))
    except Exception:
        pass  # cosmetic only; keep "python" rather than fail to start


def main() -> int:
    if sys.platform == "win32":
        # Give the taskbar our own icon instead of grouping the window under python.exe.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DumbNotes")
    elif sys.platform == "darwin":
        set_mac_app_name(APP_TITLE)
    app = QApplication(sys.argv)
    app.setApplicationName("DumbNotes")
    app.setWindowIcon(QIcon(str(ICON)))
    # Same look on Windows and macOS; light or dark is chosen in View > Dark Mode, not by
    # the system setting.
    app.setStyle("Fusion")
    apply_theme(app, "dark" if settings().value(THEME_SETTING) == "dark" else "light")
    store = open_store()
    if store is None:
        return 1
    old = old_data_dir()
    if (old / "notes.db").is_file():
        migrate_database(old / "notes.db", old / "images", store)
    window = MainWindow(store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
