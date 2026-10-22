"""Raw configuration editor with validation and backups (A9)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource  # noqa: E402

    HAS_SOURCE = True
except (ValueError, ImportError):
    HAS_SOURCE = False

from src.safe_io import atomic_write_text
from src.lang import t  # noqa: E402

HOME = Path.home()
KNOWN_FILES = (
    HOME / ".config/caelestia/shell.json",
    HOME / ".config/caelestia/monitors.lua",
    HOME / ".config/caelestia/rules.lua",
    HOME / ".config/caelestia/user-keybinds.lua",
    HOME / ".config/caelestia/hypr-user.lua",
    HOME / ".config/caelestia/hypr-vars.lua",
    HOME / ".config/caelestia/settings-overrides.lua",
    HOME / ".config/hypr/hyprland.lua",
    HOME / ".config/hypr/hyprland.conf",
    HOME / ".config/hypr/variables.lua",
    HOME / ".config/hypr/hyprland/general.lua",
    HOME / ".config/hypr/hyprland/input.lua",
    HOME / ".config/hypr/hyprland/decoration.lua",
    HOME / ".config/hypr/hyprland/animations.lua",
    HOME / ".config/hypr/hyprland/gestures.lua",
    HOME / ".config/hypr/hyprland/group.lua",
    HOME / ".config/hypr/hyprland/misc.lua",
    HOME / ".config/hypr/hyprland/env.lua",
    HOME / ".config/hypr/hyprland/execs.lua",
    HOME / ".config/caelestia-settings/hypr_overrides.json",
    HOME / ".config/caelestia-settings/hypr_extras.json",
    HOME / ".config/caelestia-settings/advanced_rules.json",
)


def _reload_hyprland() -> None:
    try:
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        pass


class ConfigEditorPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.main_window = main_window
        self._path: Path | None = None

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(10)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        self._files = Gtk.ComboBoxText()
        self._files.set_hexpand(True)
        for path in KNOWN_FILES:
            self._files.append(str(path), str(path).replace(str(HOME), "~"))
        self._files.connect("changed", self._on_file_changed)
        toolbar.append(self._files)

        reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Discard changes and reload the file"))
        reload_btn.connect("clicked", lambda _b: self._load())
        toolbar.append(reload_btn)

        save_btn = Gtk.Button(label=t("Save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _b: self._save())
        toolbar.append(save_btn)
        self.append(toolbar)

        self._status = Gtk.Label()
        self._status.add_css_class("caption")
        self._status.add_css_class("dim-label")
        self._status.set_halign(Gtk.Align.START)
        self._status.set_margin_start(14)
        self._status.set_margin_bottom(4)
        self.append(self._status)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_margin_start(12)
        scroller.set_margin_end(12)
        scroller.set_margin_bottom(12)
        self._view = GtkSource.View() if HAS_SOURCE else Gtk.TextView()
        self._view.set_monospace(True)
        self._view.set_wrap_mode(Gtk.WrapMode.NONE)
        if HAS_SOURCE:
            self._view.set_show_line_numbers(True)
            self._view.set_highlight_current_line(True)
            self._language_manager = GtkSource.LanguageManager.get_default()
        scroller.set_child(self._view)
        self.append(scroller)

        self._buffer = self._view.get_buffer()
        self._buffer.connect("changed", lambda _b: self._update_status())
        self._files.set_active(0)
        self._load()

    def _selected_path(self) -> Path | None:
        selected = self._files.get_active_id()
        return Path(selected) if selected else None

    def _on_file_changed(self, _combo) -> None:
        self._load()

    def _load(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        self._path = path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        self._buffer.set_text(text)
        if HAS_SOURCE:
            try:
                language = None
                if path.suffix == ".lua":
                    language = self._language_manager.get_language("lua")
                elif path.suffix == ".json":
                    language = self._language_manager.get_language("json")
                if language is not None:
                    self._buffer.set_language(language)
            except Exception as exc:
                print(f"GtkSource language detection failed: {exc}")
        self._update_status()

    def _update_status(self) -> None:
        start, end = self._buffer.get_bounds()
        text = self._buffer.get_text(start, end, True)
        lines = text.count("\n") + (1 if text else 0)
        suffix = self._path.suffix if self._path else ""
        note = t(" · generated file") if self._path and self._path.name.startswith("settings-overrides") else ""
        self._status.set_text(t("{lines} lines · {chars} characters · {suffix}{note}").format(lines=lines, chars=len(text), suffix=suffix, note=note))

    def _save(self) -> None:
        if self._path is None:
            return
        start, end = self._buffer.get_bounds()
        text = self._buffer.get_text(start, end, True)
        suffix = self._path.suffix.lower()

        if suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                self.main_window.add_toast(Adw.Toast.new(t("Invalid JSON: {error}").format(error=exc)))
                return
        elif suffix == ".lua":
            if not self._lua_valid(text):
                self.main_window.add_toast(Adw.Toast.new(t("Invalid Lua syntax — not saved")))
                return

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self._path, text)
        except OSError as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Save failed: {error}").format(error=exc)))
            return

        if suffix in (".lua", ".conf") and (
            str(self._path).startswith(str(HOME / ".config/hypr"))
            or self._path.name in (
                "monitors.lua", "rules.lua", "user-keybinds.lua", "hypr-user.lua", "hypr-vars.lua"
            )
        ):
            _reload_hyprland()
        self.main_window.add_toast(Adw.Toast.new(t("Saved {name}").format(name=self._path.name)))
        self._update_status()

    @staticmethod
    def _lua_valid(text: str) -> bool:
        luac = shutil.which("luac")
        if not luac:
            return True
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as handle:
            handle.write(text)
            temp_path = handle.name
        try:
            return subprocess.run([luac, "-p", temp_path], capture_output=True).returncode == 0
        finally:
            Path(temp_path).unlink(missing_ok=True)
