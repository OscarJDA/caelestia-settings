"""Safe configuration writes, rotating backups and an undo/redo history.

Every write goes through here so a bad value (or a crashed app) can never
leave a half-written config behind:

* writes go to a temp file in the same directory and are moved into place
  atomically;
* the previous version is copied to a per-app backup directory before the
  write (the newest 10 versions per file are kept);
* changes can be undone/redone from the main window.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

APP_CONFIG_DIR = Path(os.path.expanduser("~/.config/caelestia-settings"))
BACKUP_DIR = APP_CONFIG_DIR / "backups"
BACKUP_KEEP = 10


# ── Backups & atomic writes ──────────────────────────────────────────────────


def _backup_dir_for(path: Path) -> Path:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:10]
    return BACKUP_DIR / f"{path.name}.{digest}"


def backup_file(path: Path, keep: int = BACKUP_KEEP) -> Path | None:
    """Copy ``path`` into the backup directory, pruning old versions."""
    try:
        if not path.exists() or not path.is_file():
            return None
        target_dir = _backup_dir_for(path)
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = target_dir / f"{stamp}.bak"
        shutil.copy2(path, target)
        old = sorted(target_dir.glob("*.bak"))
        for stale in old[:-keep]:
            stale.unlink(missing_ok=True)
        return target
    except OSError as exc:
        print(f"Backup fehlgeschlagen für {path}: {exc}")
        return None


def atomic_write_text(path: Path, text: str) -> bool:
    """Write ``text`` atomically. Returns False when nothing changed."""
    try:
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return False
    except (OSError, UnicodeDecodeError):
        pass

    path.parent.mkdir(parents=True, exist_ok=True)
    backup_file(path)
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        mode = 0o644

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        return True
    finally:
        tmp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, data: dict) -> bool:
    return atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path, default: dict | None = None) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"JSON lesen fehlgeschlagen für {path}: {exc}")
    return {} if default is None else default


# ── Undo / redo ──────────────────────────────────────────────────────────────


@dataclass
class _HistoryEntry:
    label: str
    undo: Callable[[], None]
    redo: Callable[[], None]


class History:
    """Small in-memory undo stack shared by all settings pages."""

    def __init__(self, limit: int = 50) -> None:
        self._limit = limit
        self._undo_stack: list[_HistoryEntry] = []
        self._redo_stack: list[_HistoryEntry] = []
        self._listeners: list[Callable[[], None]] = []
        self._lock = threading.RLock()

    # Listeners are used by the header buttons to refresh their sensitivity.
    def add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception as exc:  # a broken listener must not break writes
                print(f"History-Listener fehlgeschlagen: {exc}")

    def push(self, label: str, undo: Callable[[], None], redo: Callable[[], None]) -> None:
        with self._lock:
            self._undo_stack.append(_HistoryEntry(label, undo, redo))
            if len(self._undo_stack) > self._limit:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
        self._notify()

    def undo(self) -> str | None:
        with self._lock:
            if not self._undo_stack:
                return None
            entry = self._undo_stack.pop()
            self._redo_stack.append(entry)
        try:
            entry.undo()
        except Exception as exc:
            print(f"Undo fehlgeschlagen ({entry.label}): {exc}")
        self._notify()
        return entry.label

    def redo(self) -> str | None:
        with self._lock:
            if not self._redo_stack:
                return None
            entry = self._redo_stack.pop()
            self._undo_stack.append(entry)
        try:
            entry.redo()
        except Exception as exc:
            print(f"Redo fehlgeschlagen ({entry.label}): {exc}")
        self._notify()
        return entry.label

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def next_undo_label(self) -> str:
        return self._undo_stack[-1].label if self._undo_stack else ""

    def next_redo_label(self) -> str:
        return self._redo_stack[-1].label if self._redo_stack else ""


HISTORY = History()
