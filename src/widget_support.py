"""Detect and install the desktop widget module in a Caelestia shell.

The settings app only writes ``desktop_widgets.json``; the cards themselves are
QML that lives in the shell.  This module copies the bundled widget files into
the user's Quickshell config and adds ``DesktopWidgets {}`` to ``shell.qml`` so
the page works with a stock Caelestia installation as well.

A timestamped backup of ``shell.qml`` and of any replaced widget files is kept
under ``<shell>/.widget-support-backup/``.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

FORK_URL = "https://github.com/OscarJDA/caelestia-shell-fork"
SHELL_DIR_ENV = "CAELESTIA_SHELL_DIR"

_ENTRY_RE = re.compile(r"^\s*DesktopWidgets\s*\{", re.MULTILINE)
_BLOCK_RE = re.compile(r"^(\s*)(Background|Drawers)\b[^\n]*\{")

_REQUIRED = ("DesktopWidgets.qml", "WidgetCatalog.js", "WidgetCard.qml")


class WidgetSupportError(RuntimeError):
    """Raised when the widget module cannot be installed."""


@dataclass
class InstallResult:
    backup: Path
    files: list[str]
    patched: bool


def bundled_dir() -> Path:
    return Path(__file__).resolve().parent / "shell_widgets"


def bundle_files() -> list[str]:
    directory = bundled_dir()
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.iterdir() if path.suffix in (".qml", ".js"))


def shell_dir() -> Path:
    override = os.environ.get(SHELL_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    config = Path(base).expanduser() if base else Path.home() / ".config"
    return config / "quickshell" / "caelestia"


def module_dir(shell: Path | None = None) -> Path:
    return (shell or shell_dir()) / "modules" / "background"


def is_installed(shell: Path | None = None) -> bool:
    """True when the shell QML contains the widget module and its entry point."""
    shell = shell or shell_dir()
    module = module_dir(shell)
    if not all((module / name).is_file() for name in _REQUIRED):
        return False
    try:
        text = (shell / "shell.qml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(_ENTRY_RE.search(text))


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _patched_shell(text: str) -> tuple[str, bool]:
    """Return ``(text, changed)`` with a ``DesktopWidgets {}`` entry point."""
    if _ENTRY_RE.search(text):
        return text, False

    lines = text.splitlines(keepends=True)
    for name, after in (("Background", True), ("Drawers", False)):
        for index, line in enumerate(lines):
            match = _BLOCK_RE.match(line)
            if not match or match.group(2) != name:
                continue
            indent = match.group(1)
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            entry = f"{indent}DesktopWidgets {{}}{eol}"
            position = _block_end(lines, index) + 1 if after else index
            lines.insert(position, entry)
            return "".join(lines), True

    raise WidgetSupportError("shell.qml has no Background or Drawers block")


def _block_end(lines: list[str], start: int) -> int:
    """Return the line index where the QML block opened at ``start`` closes."""
    depth = 0
    opened = False
    for position in range(start, len(lines)):
        for char in lines[position]:
            if char == "{":
                depth += 1
                opened = True
            elif char == "}":
                depth -= 1
                if opened and depth <= 0:
                    return position
    return start


def install(shell: Path | None = None) -> InstallResult:
    """Copy the bundled QML into ``shell`` and register it in ``shell.qml``."""
    shell = (shell or shell_dir()).expanduser()
    shell_qml = shell / "shell.qml"
    module = module_dir(shell)

    if not shell_qml.is_file():
        raise WidgetSupportError(f"no shell.qml found in {shell}")
    if not module.is_dir():
        raise WidgetSupportError(f"no modules/background directory in {shell}")

    files = bundle_files()
    missing = [name for name in files if not (bundled_dir() / name).is_file()]
    if not files or missing:
        raise WidgetSupportError("the bundled widget files are missing")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = shell / ".widget-support-backup" / stamp
    suffix = 1
    while backup.exists():
        backup = shell / ".widget-support-backup" / f"{stamp}-{suffix}"
        suffix += 1
    backup.mkdir(parents=True)
    shutil.copy2(shell_qml, backup / "shell.qml")

    replaced: dict[str, bool] = {}
    for name in files:
        target = module / name
        replaced[name] = target.exists()
        if replaced[name]:
            shutil.copy2(target, backup / name)

    try:
        for name in files:
            shutil.copy2(bundled_dir() / name, module / name)

        original = _read_text(shell_qml)
        patched, changed = _patched_shell(original)
        if changed:
            _write_text(shell_qml, patched)
    except Exception:
        for name, existed in replaced.items():
            target = module / name
            if existed:
                shutil.copy2(backup / name, target)
            elif target.exists():
                target.unlink()
        shutil.copy2(backup / "shell.qml", shell_qml)
        raise

    return InstallResult(backup=backup, files=files, patched=changed)
