from src.config import CAELESTIA_SHELL_JSON
from src.settings_editors import FieldSpec, add_object_list
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import BATTERY_WARN_DEFAULTS, IDLE_TIMEOUT_DEFAULTS, POWER_SPEC
from src.lang import t  # noqa: E402

from pathlib import Path
import shutil
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

IDLE_FIELDS = [
    FieldSpec("enabled", "Enabled", kind="bool", default=True),
    FieldSpec("timeout", "Timeout", kind="int", default=300, minimum=10, maximum=86400, subtitle="Seconds"),
    FieldSpec("idleAction", "Idle action", kind="action", subtitle="e.g. lock, dpms off, suspendThenHibernate"),
    FieldSpec("returnAction", "Return action", kind="action", subtitle="Runs when activity resumes"),
    FieldSpec("inhibitWhenAudio", "Inhibit while audio plays", kind="bool", default=False),
    FieldSpec("inhibitWhenCharging", "Inhibit while charging", kind="bool", default=False),
    FieldSpec("respectInhibitors", "Respect inhibitors", kind="bool", default=True),
]

BATTERY_FIELDS = [
    FieldSpec("level", "Battery level", kind="int", default=20, minimum=0, maximum=100, subtitle="Percent"),
    FieldSpec("title", "Title"),
    FieldSpec("message", "Message"),
    FieldSpec("icon", "Material icon"),
    FieldSpec("critical", "Critical warning", kind="bool", default=False),
]


class PowerPage(SettingsPage):
    def __init__(self, main_window):
        backend = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(main_window, POWER_SPEC, backend, custom_builders=[self._build_custom])

    def _build_custom(self, page):
        backend = self.backend
        add_object_list(
            page,
            backend,
            "general.idle.timeouts",
            IDLE_TIMEOUT_DEFAULTS,
            IDLE_FIELDS,
            "Idle timeouts",
            "Actions performed after inactivity. Entries are evaluated in order.",
            title_key="idleAction",
            new_item={
                "enabled": True,
                "timeout": 300,
                "idleAction": "lock",
                "returnAction": "",
                "inhibitWhenAudio": False,
                "inhibitWhenCharging": False,
                "respectInhibitors": True,
            },
        )
        add_object_list(
            page,
            backend,
            "general.battery.warnLevels",
            BATTERY_WARN_DEFAULTS,
            BATTERY_FIELDS,
            "Battery warnings",
            "Notifications shown when the battery reaches these levels.",
            title_key="title",
            new_item={
                "level": 15,
                "title": "Low battery",
                "message": "You might want to plug in a charger",
                "icon": "battery_android_frame_2",
                "critical": False,
            },
        )

        self._build_power_profile(page)

    def _build_power_profile(self, page) -> None:
        group = Adw.PreferencesGroup(
            title=t("Power profile"),
            description=t("Provided by power-profiles-daemon."),
        )
        profile_row = Adw.ActionRow(title=t("Profile"))
        self._profile_combo = Gtk.ComboBoxText()
        self._profile_combo.set_valign(Gtk.Align.CENTER)
        for value, label in (("performance", t("Performance")), ("balanced", t("Balanced")), ("power-saver", t("Power saver"))):
            self._profile_combo.append(value, label)
        profile_row.add_suffix(self._profile_combo)
        group.add(profile_row)

        self._battery_row = Adw.ActionRow(title=t("Battery"), subtitle=t("No battery detected"))
        group.add(self._battery_row)
        page.add(group)

        session = Adw.PreferencesGroup(title=t("Session"))
        suspend_row = Adw.ActionRow(title=t("Suspend"), subtitle=t("Suspend the system"))
        suspend_btn = Gtk.Button(label=t("Suspend"))
        suspend_btn.set_valign(Gtk.Align.CENTER)
        suspend_btn.connect("clicked", lambda _b: self._session_action("suspend"))
        suspend_row.add_suffix(suspend_btn)
        session.add(suspend_row)

        hibernate_row = Adw.ActionRow(title=t("Hibernate"), subtitle=t("Hibernate the system"))
        hibernate_btn = Gtk.Button(label=t("Hibernate"))
        hibernate_btn.set_valign(Gtk.Align.CENTER)
        hibernate_btn.connect("clicked", lambda _b: self._session_action("hibernate"))
        hibernate_row.add_suffix(hibernate_btn)
        session.add(hibernate_row)
        page.add(session)

        self._load_profile()
        self._refresh_battery()
        GLib.timeout_add_seconds(5, self._refresh_battery)

    def _load_profile(self) -> None:
        if not shutil.which("powerprofilesctl"):
            self._profile_combo.set_sensitive(False)
            self._profile_combo.append("unavailable", t("power-profiles-daemon not installed"))
            self._profile_combo.set_active_id("unavailable")
            return
        try:
            current = subprocess.run(
                ["powerprofilesctl", "get"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            current = ""
        if current and not self._profile_combo.set_active_id(current):
            self._profile_combo.append(current, current)
            self._profile_combo.set_active_id(current)
        self._profile_combo.connect("changed", self._on_profile_changed)

    def _on_profile_changed(self, combo) -> None:
        value = combo.get_active_id()
        if not value or value == "unavailable":
            return
        try:
            subprocess.run(["powerprofilesctl", "set", value], check=True, timeout=5)
            self.main_window.add_toast(Adw.Toast.new(t("Power profile: {value}").format(value=t(value))))
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Could not set profile: {error}").format(error=exc)))

    def _refresh_battery(self) -> bool:
        supplies = Path("/sys/class/power_supply")
        batteries = list(supplies.glob("BAT*")) if supplies.exists() else []
        if not batteries:
            self._battery_row.set_subtitle(t("No battery detected"))
            return True
        battery = batteries[0]
        try:
            capacity = (battery / "capacity").read_text().strip()
            status = (battery / "status").read_text().strip()
            self._battery_row.set_subtitle(f"{capacity}% · {status}")
        except OSError:
            self._battery_row.set_subtitle(t("Battery information unavailable"))
        return True

    def _session_action(self, action: str) -> None:
        dialog = Adw.AlertDialog(
            heading=f"{action.title()}?",
            body=f"The system will {action} now.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("go", action.title())
        dialog.set_response_appearance("go", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_dialog, response: str) -> None:
            if response == "go":
                subprocess.Popen(["systemctl", action])

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
