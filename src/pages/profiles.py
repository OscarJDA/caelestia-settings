"""Configuration profiles: export, import and reset (A6)."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.hypr_settings import EXTRAS_JSON, OVERRIDES_JSON, HyprBackend
from src.safe_io import atomic_write_text, backup_file
from src.lang import t  # noqa: E402

FORMAT = "caelestia-settings-profile"
VERSION = 1

# Files included in a profile. Paths are relative to $HOME.
INCLUDE_PATTERNS = (
    ".config/caelestia/shell.json",
    ".config/caelestia/hypr-user.lua",
    ".config/caelestia/hypr-vars.lua",
    ".config/caelestia/monitors.lua",
    ".config/caelestia/monitors/*/shell.json",
    ".config/caelestia/rules.lua",
    ".config/caelestia/user-keybinds.lua",
    ".config/caelestia/settings-overrides.lua",
    ".config/caelestia-settings/*.json",
    ".config/hypr/hyprland/monitors.conf",
    ".config/hypr/hyprland/rules.conf",
    ".config/hypr/hyprland/keybinds.conf",
    ".config/hypr/variables.lua",
)

ALLOWED_ROOTS = (
    ".config/caelestia/",
    ".config/caelestia-settings/",
    ".config/hypr/hyprland/",
    ".config/hypr/variables.lua",
)


def _collect_files() -> dict[str, str]:
    home = Path.home()
    files: dict[str, str] = {}
    for pattern in INCLUDE_PATTERNS:
        for path in sorted(home.glob(pattern)):
            if not path.is_file() or "/backups/" in str(path):
                continue
            try:
                relative = path.relative_to(home)
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            files[str(relative)] = text
    return files


def _is_allowed(relative: str) -> bool:
    relative = relative.lstrip("/")
    if ".." in Path(relative).parts:
        return False
    return any(relative == root.rstrip("/") or relative.startswith(root) for root in ALLOWED_ROOTS)


class ProfilesPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build()

    def _build(self) -> None:
        group = Adw.PreferencesGroup(
            title=t("Backup and restore"),
            description=t("Profiles are JSON files containing the Caelestia and Hyprland files managed by this app."),
        )
        export_row = Adw.ActionRow(
            title=t("Export profile"),
            subtitle=t("Save a backup of shell.json, overrides, monitor configs and keybinds"),
        )
        export_btn = Gtk.Button(label=t("Export"))
        export_btn.set_valign(Gtk.Align.CENTER)
        export_btn.add_css_class("suggested-action")
        export_btn.connect("clicked", lambda _b: self._export())
        export_row.add_suffix(export_btn)
        group.add(export_row)

        import_row = Adw.ActionRow(
            title=t("Import profile"),
            subtitle=t("Restore files from a previously exported profile"),
        )
        import_btn = Gtk.Button(label=t("Import"))
        import_btn.set_valign(Gtk.Align.CENTER)
        import_btn.connect("clicked", lambda _b: self._import())
        import_row.add_suffix(import_btn)
        group.add(import_row)

        info = Adw.ActionRow(
            title=t("What is included"),
            subtitle=t("{patterns} patterns · current files: {files}").format(patterns=len(INCLUDE_PATTERNS), files=len(_collect_files())),
        )
        group.add(info)
        self.add(group)

        reset_group = Adw.PreferencesGroup(
            title=t("Reset"),
            description=t("Removes generated overrides. Existing files are backed up first."),
        )
        reset_overrides = Adw.ActionRow(
            title=t("Reset Hyprland overrides"),
            subtitle=t("Delete animation/gesture/config overrides and reload the base configuration"),
        )
        btn1 = Gtk.Button(label=t("Reset"))
        btn1.add_css_class("destructive-action")
        btn1.set_valign(Gtk.Align.CENTER)
        btn1.connect("clicked", lambda _b: self._reset_overrides())
        reset_overrides.add_suffix(btn1)
        reset_group.add(reset_overrides)

        reset_monitors = Adw.ActionRow(
            title=t("Remove all per-monitor overrides"),
            subtitle=t("Delete every monitor's shell.json override file"),
        )
        btn2 = Gtk.Button(label=t("Remove"))
        btn2.add_css_class("destructive-action")
        btn2.set_valign(Gtk.Align.CENTER)
        btn2.connect("clicked", lambda _b: self._reset_monitors())
        reset_monitors.add_suffix(btn2)
        reset_group.add(reset_monitors)
        self.add(reset_group)

    # ── Export ────────────────────────────────────────────────────────────

    def _export(self) -> None:
        dialog = Gtk.FileDialog(title=t("Export Caelestia profile"))
        dialog.set_initial_name(f"caelestia-profile-{datetime.now():%Y%m%d-%H%M}.json")
        dialog.save(self.get_root(), None, self._on_export_done)

    def _on_export_done(self, dialog, result) -> None:
        try:
            file = dialog.save_finish(result)
        except Exception:
            return
        path = Path(file.get_path())
        bundle = {
            "format": FORMAT,
            "version": VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "host": os.uname().nodename,
            "files": _collect_files(),
        }
        try:
            path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.main_window.add_toast(Adw.Toast.new(t("Profile exported to {name}").format(name=path.name)))
        except OSError as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Export failed: {error}").format(error=exc)))

    # ── Import ────────────────────────────────────────────────────────────

    def _import(self) -> None:
        dialog = Gtk.FileDialog(title=t("Import Caelestia profile"))
        file_filter = Gtk.FileFilter()
        file_filter.set_name(t("Caelestia profile (*.json)"))
        file_filter.add_pattern("*.json")
        dialog.set_default_filter(file_filter)
        dialog.open(self.get_root(), None, self._on_import_done)

    @staticmethod
    def _json_filter():
        file_filter = Gtk.FileFilter()
        file_filter.set_name(t("Caelestia profile (*.json)"))
        file_filter.add_pattern("*.json")
        return file_filter

    def _on_import_done(self, dialog, result) -> None:
        try:
            file = dialog.open_finish(result)
        except Exception:
            return
        try:
            bundle = json.loads(Path(file.get_path()).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Invalid profile: {error}").format(error=exc)))
            return
        if bundle.get("format") != FORMAT or not isinstance(bundle.get("files"), dict):
            self.main_window.add_toast(Adw.Toast.new(t("Unsupported profile format")))
            return

        files = {
            rel: text
            for rel, text in bundle["files"].items()
            if isinstance(rel, str) and isinstance(text, str) and _is_allowed(rel)
        }
        if not files:
            self.main_window.add_toast(Adw.Toast.new(t("Profile contains no importable files")))
            return

        alert = Adw.AlertDialog(
            heading=t("Import profile?"),
            body=t("{count} files will be restored. Existing files are backed up first.").format(count=len(files)),
        )
        alert.add_response("cancel", t("Cancel"))
        alert.add_response("import", t("Import"))
        alert.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)
        alert.set_default_response("import")
        alert.set_close_response("cancel")

        def on_response(_dialog, response: str) -> None:
            if response == "import":
                self._restore(files)

        alert.connect("response", on_response)
        alert.present(self.get_root())

    def _restore(self, files: dict[str, str]) -> None:
        home = Path.home()
        written = 0
        errors = []
        for relative, text in files.items():
            target = home / relative
            if not _is_allowed(relative):
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    backup_file(target)
                atomic_write_text(target, text)
                written += 1
            except OSError as exc:
                errors.append(f"{relative}: {exc}")
        try:
            HyprBackend().ensure_loaded()
            subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
        except Exception as exc:
            errors.append(str(exc))
        message = t("Imported {count} file(s)").format(count=written)
        if errors:
            message += t(" — {count} error(s)").format(count=len(errors))
        self.main_window.add_toast(Adw.Toast.new(message))

    # ── Reset ─────────────────────────────────────────────────────────────

    def _reset_overrides(self) -> None:
        for path in (OVERRIDES_JSON, EXTRAS_JSON):
            if path.exists():
                backup_file(path)
                path.unlink(missing_ok=True)
        backend = HyprBackend()
        backend._persist({})
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
        self.main_window.add_toast(Adw.Toast.new(t("Hyprland overrides reset")))

    def _reset_monitors(self) -> None:
        removed = 0
        for path in sorted((Path.home() / ".config/caelestia/monitors").glob("*/shell.json")):
            backup_file(path)
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        self.main_window.add_toast(Adw.Toast.new(t("Removed {count} monitor override file(s)").format(count=removed)))
