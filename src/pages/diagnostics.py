"""Configuration diagnostics and validation (A5 / E5)."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from src.config import (
    CAELESTIA_HYPR_USER,
    CAELESTIA_RULES_LUA,
    CAELESTIA_SHELL_JSON,
    HYPR_CONF,
    HYPR_LUA_CONF,
)
from src.hypr_settings import LUA_OVERRIDES, OVERRIDES_JSON
from src.lang import t  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


class DiagnosticsPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._report = ""

        self._env_group = Adw.PreferencesGroup(title=t("Environment"))
        self._checks_group = Adw.PreferencesGroup(title=t("Configuration checks"))
        self._actions_group = Adw.PreferencesGroup(title=t("Actions"))
        self._env_rows: list[Gtk.Widget] = []
        self._check_rows: list[Gtk.Widget] = []
        self.add(self._env_group)
        self.add(self._checks_group)
        self.add(self._actions_group)

        self._add_action(
            "Re-run checks",
            "Validate the current configuration again",
            "Recheck",
            self.refresh,
        )
        self._add_action(
            "Run Hyprland doctor",
            "Checks the Super+I bind, sourced config files and Polkit agent",
            "Run",
            self._run_doctor,
        )
        self._add_action(
            "Reload Hyprland",
            "Apply the current configuration files",
            "Reload",
            self._reload_hyprland,
        )
        self._add_action(
            "Copy report",
            "Copy the diagnostics report to the clipboard",
            "Copy",
            self._copy_report,
        )

        self.refresh()

    def _add_action(self, title: str, subtitle: str, label: str, callback) -> None:
        row = Adw.ActionRow(title=t(title), subtitle=t(subtitle))
        button = Gtk.Button(label=t(label))
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: callback())
        row.add_suffix(button)
        self._actions_group.add(row)

    def _clear(self, group: Adw.PreferencesGroup, rows: list[Gtk.Widget]) -> None:
        for row in rows:
            try:
                group.remove(row)
            except Exception:
                pass
        rows.clear()

    def _status_row(self, title: str, ok: bool, subtitle: str = "") -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle or (t("OK") if ok else t("Needs attention")))
        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic" if ok else "dialog-warning-symbolic")
        icon.add_css_class("success" if ok else "warning")
        icon.set_valign(Gtk.Align.CENTER)
        row.add_prefix(icon)
        self._checks_group.add(row)
        self._check_rows.append(row)

    def refresh(self) -> None:
        self._clear(self._env_group, self._env_rows)
        self._clear(self._checks_group, self._check_rows)
        app_version = "?"
        try:
            app_version = json.loads((APP_ROOT / "manifest.json").read_text()).get("version", "?")
        except (OSError, json.JSONDecodeError):
            pass

        rc, hypr_version = _run(["hyprctl", "version"])
        hypr_version = hypr_version.splitlines()[0] if rc == 0 and hypr_version else "not available"

        env_rows = [
            ("Caelestia Settings", f"v{app_version}"),
            ("Hyprland", hypr_version),
            ("Kernel", platform.release()),
            ("Python", platform.python_version()),
            ("Config mode", "Lua" if HYPR_LUA_CONF.exists() else ("Classic .conf" if HYPR_CONF.exists() else "Unknown")),
            ("Shell config", str(CAELESTIA_SHELL_JSON).replace(str(Path.home()), "~")),
        ]
        for title, value in env_rows:
            row = Adw.ActionRow(title=title, subtitle=value)
            self._env_group.add(row)
            self._env_rows.append(row)

        self._status_row(t("shell.json parses"), self._valid_json(CAELESTIA_SHELL_JSON))
        self._status_row(t("Advanced rules parse"), self._valid_json(Path.home() / ".config/caelestia-settings/advanced_rules.json"))
        self._status_row(t("Hyprland overrides parse"), self._valid_json(OVERRIDES_JSON))

        rc, errors = _run(["hyprctl", "configerrors"])
        self._status_row(
            t("Hyprland config errors"),
            not errors.strip() or "no errors" in errors.lower(),
            (errors.strip().splitlines()[0] if errors.strip() else t("No errors reported")),
        )

        self._status_row(t("Lua override syntax"), self._lua_syntax_ok(), t("Checked with luac -p"))
        self._status_row(
            t("Override layer loaded"),
            self._override_require_present(),
            f"pcall(require, \"settings-overrides\") in {CAELESTIA_HYPR_USER.name}",
        )
        self._status_row(t("Rules file present"), CAELESTIA_RULES_LUA.exists(), str(CAELESTIA_RULES_LUA))
        self._status_row(t("bluetoothctl available"), shutil.which("bluetoothctl") is not None)

        self._report = self._build_report(app_version, hypr_version, errors)

    def _valid_json(self, path: Path) -> bool:
        if not path.exists():
            return True
        try:
            json.loads(path.read_text())
            return True
        except (OSError, json.JSONDecodeError):
            return False

    def _lua_syntax_ok(self) -> bool:
        if not LUA_OVERRIDES.exists():
            return True
        luac = shutil.which("luac")
        if not luac:
            return True
        rc, _out = _run([luac, "-p", str(LUA_OVERRIDES)])
        return rc == 0

    def _override_require_present(self) -> bool:
        if not LUA_OVERRIDES.exists():
            return True
        try:
            return "settings-overrides" in CAELESTIA_HYPR_USER.read_text()
        except OSError:
            return False

    def _build_report(self, app_version: str, hypr_version: str, errors: str) -> str:
        lines = [
            f"Caelestia Settings {app_version}",
            f"Hyprland: {hypr_version}",
            f"Kernel: {platform.release()}",
            f"Lua mode: {HYPR_LUA_CONF.exists()}",
            "",
            "Hyprland config errors:",
            errors.strip() or "(none)",
            "",
        ]
        for path in (LUA_OVERRIDES,):
            if path.exists():
                lines.append(f"{path}:")
                lines.append(path.read_text()[:2000])
        return "\n".join(lines)

    def _run_doctor(self) -> None:
        candidates = [
            APP_ROOT / "doctor.sh",
            Path.home() / ".local/share/caelestia-settings/doctor.sh",
        ]
        script = next((path for path in candidates if path.exists()), None)
        if script is None:
            self.main_window.add_toast(Adw.Toast.new(t("doctor.sh not found")))
            return
        rc, output = _run(["bash", str(script)], timeout=20)
        dialog = Adw.AlertDialog(heading=t("Hyprland doctor"))
        label = Gtk.Label(label=output or t("Exited with {code}").format(code=rc))
        label.set_wrap(True)
        label.set_xalign(0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_size_request(620, 360)
        scroller.set_child(label)
        dialog.set_extra_child(scroller)
        dialog.add_response("close", t("Close"))
        dialog.present(self.get_root())

    def _reload_hyprland(self) -> None:
        _run(["hyprctl", "reload"])
        self.refresh()
        self.main_window.add_toast(Adw.Toast.new(t("Hyprland reloaded")))

    def _copy_report(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        display.get_clipboard().set(self._report)
        self.main_window.add_toast(Adw.Toast.new(t("Diagnostics report copied")))
