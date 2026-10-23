#!/usr/bin/env python3
"""Refresh ``src/shell_widgets`` from a Caelestia shell checkout.

The settings app bundles the QML that renders desktop widgets so it can be
installed offline.  Run this whenever the shell fork's widget module changes::

    python3 tools/sync_shell_widgets.py ../shell
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "src" / "shell_widgets"
EXTRA = (
    "DesktopWidgets.qml",
    "WidgetCatalog.js",
    "WidgetCard.qml",
    "WidgetIconButton.qml",
    "WidgetSparkline.qml",
    "WidgetStat.qml",
)


def widget_files(source: Path) -> list[Path]:
    files = [source / name for name in EXTRA]
    files += sorted(source.glob("Widget*.qml"))
    return [path for path in dict.fromkeys(files) if path.is_file()]


def source_commit(source: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print(__doc__)
        return 2
    source = Path(argv[1]).expanduser() if len(argv) == 2 else ROOT.parent / "shell" / "modules" / "background"
    source = source / "modules" / "background" if (source / "modules" / "background").is_dir() else source
    if not (source / "DesktopWidgets.qml").is_file():
        print(f"error: no DesktopWidgets.qml in {source}", file=sys.stderr)
        return 1

    files = widget_files(source)
    DEST.mkdir(parents=True, exist_ok=True)
    for path in files:
        (DEST / path.name).write_bytes(path.read_bytes())

    commit = source_commit(source)
    (DEST / "SOURCE.md").write_text(
        "# Bundled desktop widget module\n\n"
        "Copied from the Caelestia shell fork: "
        "https://github.com/OscarJDA/caelestia-shell-fork\n\n"
        "Installed into `~/.config/quickshell/caelestia` by the "
        "\"Install support\" action on the Desktop widgets page.\n\n"
        "Do not edit these files here. Refresh with:\n\n"
        "    python3 tools/sync_shell_widgets.py /path/to/shell\n\n"
        f"Source commit: {commit}\n",
        encoding="utf-8",
    )
    print(f"copied {len(files)} files from {source} (commit {commit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
