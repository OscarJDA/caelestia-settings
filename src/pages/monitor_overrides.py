"""Per-monitor Caelestia shell overrides (A8).

Caelestia reads ``~/.config/caelestia/monitors/<output>/shell.json`` after the
global ``shell.json``.  This page edits that overlay and falls back to the
global value for keys that have not been overridden yet.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.config import CAELESTIA_SHELL_JSON, parse_monitors_conf
from src.safe_io import backup_file
from src.settings_engine import OverlayShellBackend, SettingsPage, make_backend_error_toast
from src.settings_schema import MONITOR_OVERRIDE_SPEC
from src.lang import t  # noqa: E402


def list_monitors() -> list[str]:
    names: list[str] = []
    try:
        result = subprocess.run(
            ["hyprctl", "monitors", "all", "-j"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            for monitor in json.loads(result.stdout):
                name = monitor.get("name")
                if name and name not in names:
                    names.append(name)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    if not names:
        for monitor in parse_monitors_conf().get("monitors", []):
            name = monitor.get("name")
            if name and name not in names:
                names.append(name)
    return names


def monitor_override_path(monitor_name: str) -> Path:
    return Path.home() / ".config" / "caelestia" / "monitors" / monitor_name / "shell.json"


class MonitorOverridePage(SettingsPage):
    def __init__(self, main_window, monitor_name: str):
        self.monitor_name = monitor_name
        self.override_path = monitor_override_path(monitor_name)
        backend = OverlayShellBackend(
            self.override_path,
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(
            main_window,
            MONITOR_OVERRIDE_SPEC,
            backend,
            custom_builders=[self._build_custom],
        )
        self.page_title = t("Overrides: {name}").format(name=monitor_name)

    def _build_custom(self, page):
        group = Adw.PreferencesGroup(
            title=t("Monitor overrides"),
            description=f"{self.monitor_name} · {self.override_path}",
        )

        path_row = Adw.ActionRow(
            title=t("Override file"),
            subtitle=str(self.override_path).replace(str(Path.home()), "~"),
        )
        group.add(path_row)

        reset_row = Adw.ActionRow(
            title=t("Remove all overrides"),
            subtitle=t("Delete this monitor's shell.json and fall back to the global settings"),
        )
        button = Gtk.Button(label=t("Remove"))
        button.add_css_class("destructive-action")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: self._confirm_reset())
        reset_row.add_suffix(button)
        group.add(reset_row)
        page.add(group)

    def _confirm_reset(self) -> None:
        dialog = Adw.AlertDialog(
            heading=t("Remove monitor overrides?"),
            body=t("All per-monitor settings for {name} will be deleted.").format(name=self.monitor_name),
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("remove", t("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response: str) -> None:
            if response != "remove":
                return
            if self.override_path.exists():
                backup_file(self.override_path)
                self.override_path.unlink(missing_ok=True)
            self.reload_values()
            if hasattr(self.main_window, "add_toast"):
                self.main_window.add_toast(
                    Adw.Toast.new(t("Overrides for {name} removed").format(name=self.monitor_name))
                )

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
