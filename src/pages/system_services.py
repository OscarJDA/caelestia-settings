"""systemd --user service management (D8)."""

from __future__ import annotations

import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.lang import t  # noqa: E402


def _systemctl(args: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args], capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


class SystemServicesPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._rows: list[Gtk.Widget] = []
        self._loading = False
        self._group = Adw.PreferencesGroup(
            title=t("User services"),
            description=t("Services from systemctl --user. Changes apply immediately."),
        )
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text(t("Reload service list"))
        refresh.connect("clicked", lambda _b: self.refresh())
        self._group.set_header_suffix(refresh)
        self.add(self._group)
        self.refresh()

    def refresh(self) -> None:
        if self._loading:
            return
        self._loading = True
        for row in self._rows:
            try:
                self._group.remove(row)
            except Exception:
                pass
        self._rows = []
        pending = Adw.ActionRow(title=t("Loading services…"))
        self._group.add(pending)
        self._rows.append(pending)

        def worker() -> None:
            rc, out = _systemctl(["list-units", "--type=service", "--all", "--no-pager", "--no-legend"])
            units = []
            for line in out.splitlines() if rc == 0 else []:
                line = line.replace("●", " ").replace("*", " ").strip()
                parts = line.split(None, 4)
                if len(parts) < 4:
                    continue
                unit = parts[0]
                info_rc, info_out = _systemctl(
                    ["show", unit, "-p", "ActiveState", "-p", "UnitFileState"]
                )
                info = {}
                if info_rc == 0:
                    for info_line in info_out.splitlines():
                        if "=" in info_line:
                            key, value = info_line.split("=", 1)
                            info[key.strip()] = value.strip()
                active_state = info.get("ActiveState", "inactive")
                file_state = info.get("UnitFileState", "disabled")
                units.append(
                    {
                        "unit": unit,
                        "active": active_state == "active",
                        "sub": active_state,
                        "enabled": file_state.startswith("enabled"),
                    }
                )
            GLib.idle_add(self._apply, units)

        threading.Thread(target=worker, daemon=True).start()

    def _apply(self, units: list[dict]) -> bool:
        for row in self._rows:
            try:
                self._group.remove(row)
            except Exception:
                pass
        self._rows = []

        if not units:
            row = Adw.ActionRow(title=t("No user services found"))
            self._group.add(row)
            self._rows.append(row)
            self._loading = False
            return False

        for unit in sorted(units, key=lambda item: item["unit"]):
            row = Adw.ActionRow(
                title=unit["unit"],
                subtitle=f"{t('active') if unit['active'] else t('inactive')}  ·  "
                f"{t('enabled') if unit['enabled'] else t('disabled')}",
            )
            switch = Gtk.Switch()
            switch.set_valign(Gtk.Align.CENTER)
            switch.set_active(unit["enabled"])
            switch.set_tooltip_text(t("Enable or disable at login"))
            switch.connect("notify::active", self._on_enable, unit)
            row.add_suffix(switch)
            button = Gtk.Button(label=t("Stop") if unit["active"] else t("Start"))
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", self._on_start_stop, unit)
            row.add_suffix(button)
            self._group.add(row)
            self._rows.append(row)
        self._loading = False
        return False

    def _on_enable(self, switch, _pspec, unit: dict) -> None:
        action = "enable" if switch.get_active() else "disable"
        rc, out = _systemctl([action, unit["unit"]])
        if rc != 0:
            self.main_window.add_toast(Adw.Toast.new(t("{action} failed: {error}").format(action=action, error=out[:120])))
        self.refresh()

    def _on_start_stop(self, _button, unit: dict) -> None:
        action = "stop" if unit["active"] else "start"
        rc, out = _systemctl([action, unit["unit"]])
        if rc != 0:
            self.main_window.add_toast(Adw.Toast.new(t("{action} failed: {error}").format(action=action, error=out[:120])))
        self.refresh()
