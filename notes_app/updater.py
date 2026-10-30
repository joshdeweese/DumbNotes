"""One-click update for a copy of DumbNotes cloned from GitHub (Options > Check for Updates).

Fetches from GitHub, lists what's new, fast-forwards this checkout, reinstalls the requirements
if they changed, and restarts the app. Notes aren't touched: they live in the notes folder.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QProcess

PROJECT = Path(__file__).resolve().parent.parent
# Apps opened from the Dock or Finder don't get the shell's PATH, so look for Homebrew's git
# first: it's the one whose saved GitHub login is in the keychain.
HOMEBREW_GIT = ["/opt/homebrew/bin/git", "/usr/local/bin/git"]
WINDOWS_GIT = r"C:\Program Files\Git\cmd\git.exe"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # no console window flashing up


class UpdateError(Exception):
    pass


def find_git() -> str | None:
    for git in HOMEBREW_GIT:
        if os.path.isfile(git):
            return git
    return shutil.which("git") or (WINDOWS_GIT if os.path.isfile(WINDOWS_GIT) else None)


def available() -> bool:
    """True if this copy can update itself: it's a git checkout and git is installed."""
    return (PROJECT / ".git").exists() and find_git() is not None


def _run(args: list[str], timeout: int = 60) -> str:
    # GIT_TERMINAL_PROMPT=0: fail instead of waiting for a password nobody can type.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(args, cwd=PROJECT, env=env, capture_output=True, text=True,
                                timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise UpdateError(str(e)) from e
    if result.returncode != 0:
        raise UpdateError(result.stderr.strip() or result.stdout.strip()
                          or f"{Path(args[0]).name} failed")
    return result.stdout


def _git(*args: str, timeout: int = 60) -> str:
    return _run([find_git(), *args], timeout)


def check() -> list[str]:
    """Fetch from GitHub; the summaries of the commits this copy doesn't have yet, newest first."""
    _git("fetch", "--quiet")
    try:
        _git("rev-parse", "--abbrev-ref", "@{upstream}")
    except UpdateError:
        raise UpdateError("This copy isn't following a branch on GitHub.") from None
    return _git("log", "--format=%s", "HEAD..@{upstream}").splitlines()


def update() -> None:
    """Bring this copy up to date, installing new requirements if requirements.txt changed."""
    before = _git("rev-parse", "HEAD").strip()
    _git("merge", "--ff-only", "--quiet", "@{upstream}")
    changed = _git("diff", "--name-only", before, "HEAD").splitlines()
    if "requirements.txt" in changed:
        _run([sys.executable, "-m", "pip", "install", "--quiet", "-r", "requirements.txt"],
             timeout=600)


def mac_bundle() -> Path | None:
    """The DumbNotes.app (made by make_mac_app.py) this is running from, if any."""
    exe = Path(QCoreApplication.applicationFilePath())
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent if parent.name != "Python.app" else None
    return None


def restart() -> None:
    """Start a fresh copy of the app (call after closing the window, so the note is saved)."""
    bundle = mac_bundle() if sys.platform == "darwin" else None
    if bundle:
        QProcess.startDetached("open", ["-n", str(bundle)])
    else:
        QProcess.startDetached(sys.executable, [str(PROJECT / "main.py")], str(PROJECT))
