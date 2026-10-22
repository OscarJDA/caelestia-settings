"""Default applications for Caelestia and Hyprland variables (D6)."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.config import CAELESTIA_HYPR_VARS, CAELESTIA_SHELL_JSON
from src.hypr_vars import HYPR_VARIABLES, get_hypr_variable, set_hypr_variable
from src.lang import t  # noqa: E402
from src.safe_io import atomic_write_text
from src.settings_core import lua_quote
from src.settings_engine import ShellBackend

CAELESTIA_APPS = (
    ("terminal", "Terminal"),
    ("explorer", "File explorer"),
    ("audio", "Audio settings"),
    ("playback", "Media player"),
)

CAELESTIA_DEFAULTS = {
    "terminal": ["foot"],
    "explorer": ["thunar"],
    "audio": ["pwvucontrol"],
    "playback": ["mpv"],
}

HYPR_APPS = (
    ("terminal", "Terminal"),
    ("browser", "Browser"),
    ("editor", "Editor"),
    ("fileExplorer", "File explorer"),
    ("audioSettings", "Audio settings"),
)

HYPR_DEFAULTS = {
    "terminal": "foot",
    "browser": "firefox",
    "editor": "codium",
    "fileExplorer": "thunar",
    "audioSettings": "pwvucontrol",
}

def _format_command(value) -> str:
    if isinstance(value, (list, tuple)):
        return shlex.join(str(part) for part in value)
    return "" if value is None else str(value)


def _parse_command(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return [text]


def _read_hypr_vars() -> str:
    try:
        return CAELESTIA_HYPR_VARS.read_text(encoding="utf-8")
    except OSError:
        return "return {}\n"


def _set_legacy_hypr_var(key: str, value: str) -> bool:
    """Write the old ~/.config/caelestia/hypr-vars.lua format.

    Caelestia 2.5+ reads ~/.config/hypr/variables.lua instead; this is only a
    fallback for installations that do not have that file yet.
    """
    text = _read_hypr_vars()
    quoted = lua_quote(value)
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(lambda m: m.group(1) + quoted, text, count=1)
    elif re.search(r"return\s*\{", text):
        close = text.rfind("}")
        if close == -1:
            return False
        prefix = text[:close].rstrip()
        if not prefix.endswith(("{", ",")):
            prefix += ","
        text = f"{prefix}\n    {key} = {quoted},\n{text[close:]}"
    else:
        text = f"return {{\n    {key} = {quoted},\n}}\n"

    luac = shutil.which("luac")
    if luac:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as handle:
            handle.write(text)
            temp_path = handle.name
        try:
            if subprocess.run([luac, "-p", temp_path], capture_output=True).returncode != 0:
                return False
        finally:
            Path(temp_path).unlink(missing_ok=True)
    atomic_write_text(CAELESTIA_HYPR_VARS, text)
    return True


class DefaultAppsPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.backend = ShellBackend(CAELESTIA_SHELL_JSON)
        self._caelestia_entries: dict[str, Adw.EntryRow] = {}
        self._hypr_entries: dict[str, Adw.EntryRow] = {}
        self._build()

    def _build(self) -> None:
        group = Adw.PreferencesGroup(
            title=t("Caelestia applications"),
            description=t("Used by the shell for terminal, file manager, media and audio shortcuts."),
        )
        for key, label in CAELESTIA_APPS:
            row = Adw.EntryRow(title=t(label))
            row.set_show_apply_button(True)
            value = self.backend.get(f"general.apps.{key}", default=None)
            row.set_text(_format_command(value if value else CAELESTIA_DEFAULTS.get(key, [])))
            row.connect("apply", lambda r, k=key: self._save_caelestia(k, r))
            focus = Gtk.EventControllerFocus.new()
            focus.connect("leave", lambda _c, r=row, k=key: self._save_caelestia(k, r))
            row.add_controller(focus)
            group.add(row)
            self._caelestia_entries[key] = row
        self.add(group)

        hypr_group = Adw.PreferencesGroup(
            title=t("Hyprland application variables"),
            description=t("Written to variables.lua and applied on the next Hyprland reload."),
        )
        for key, label in HYPR_APPS:
            row = Adw.EntryRow(title=t(label))
            row.set_show_apply_button(True)
            row.set_text(self._read_hypr_value(key))
            row.connect("apply", lambda r, k=key: self._save_hypr(k, r))
            focus = Gtk.EventControllerFocus.new()
            focus.connect("leave", lambda _c, r=row, k=key: self._save_hypr(k, r))
            row.add_controller(focus)
            hypr_group.add(row)
            self._hypr_entries[key] = row
        self.add(hypr_group)

    def _read_hypr_value(self, key: str) -> str:
        value = get_hypr_variable(key, None)
        if value is not None:
            return str(value)
        # Older Caelestia releases used hypr-vars.lua; keep reading it as a
        # fallback so upgrading the app does not show empty fields.
        match = re.search(rf"\b{re.escape(key)}\s*=\s*[\"']([^\"']*)[\"']", _read_hypr_vars())
        if match:
            return match.group(1)
        return HYPR_DEFAULTS.get(key, "")

    def _save_caelestia(self, key: str, row: Adw.EntryRow) -> None:
        value = _parse_command(row.get_text())
        self.backend.set(f"general.apps.{key}", value, label=t("Default {key}").format(key=key))

    def _save_hypr(self, key: str, row: Adw.EntryRow) -> None:
        value = row.get_text().strip()
        if HYPR_VARIABLES.exists():
            ok = set_hypr_variable(key, value)
        else:
            ok = _set_legacy_hypr_var(key, value)
        if not ok:
            self.main_window.add_toast(
                Adw.Toast.new(t("Could not update variables.lua ({key})").format(key=key))
            )
            return
        try:
            subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass
        self.main_window.add_toast(Adw.Toast.new(t("Updated {key}").format(key=key)))
