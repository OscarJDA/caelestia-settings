"""Read and write top-level variables in Hyprland's ``variables.lua``.

Caelestia generates ``~/.config/hypr/variables.lua`` and its keybinds read
values such as ``volumeStep`` and ``volumeMax`` from it.  The Caelestia shell
has its own equivalents (``services.audioIncrement`` / ``services.maxVolume``),
so the settings app keeps both in sync when the user changes the volume step
or the maximum volume.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.safe_io import atomic_write_text

HYPR_VARIABLES = Path.home() / ".config" / "hypr" / "variables.lua"


def _read() -> str:
    try:
        return HYPR_VARIABLES.read_text(encoding="utf-8")
    except OSError:
        return ""


def get_hypr_variable(key: str, default: Any = None) -> Any:
    """Return a simple top-level variable from variables.lua."""
    match = re.search(
        rf"^\s*{re.escape(key)}\s*=\s*([^,\n]+)",
        _read(),
        re.MULTILINE,
    )
    if not match:
        return default
    raw = match.group(1).strip()
    if raw in ("true", "false"):
        return raw == "true"
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return default


def _render(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def set_hypr_variable(key: str, value: Any) -> bool:
    """Update one top-level variable, preserving the rest of the file."""
    text = _read()
    if not text:
        return False

    rendered = _render(value)
    pattern = re.compile(
        rf"^(\s*{re.escape(key)}\s*=\s*)([^,\n]*?)(\s*),?\s*$",
        re.MULTILINE,
    )
    if pattern.search(text):
        text = pattern.sub(lambda m: f"{m.group(1)}{rendered}{m.group(3)},", text, count=1)
    else:
        close = text.rfind("}")
        if close == -1:
            return False
        prefix = text[:close].rstrip()
        if not prefix.endswith(("{", ",")):
            prefix += ","
        text = f"{prefix}\n    {key} = {rendered},\n{text[close:]}"

    luac = shutil.which("luac")
    if luac:
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as handle:
            handle.write(text)
            temp_path = handle.name
        try:
            if subprocess.run([luac, "-p", temp_path], capture_output=True).returncode != 0:
                return False
        finally:
            Path(temp_path).unlink(missing_ok=True)

    return atomic_write_text(HYPR_VARIABLES, text)
