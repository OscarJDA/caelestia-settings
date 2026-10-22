"""Ethernet, VPN, hotspot and IPv4 configuration via NetworkManager (D5)."""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.lang import t  # noqa: E402


def _nmcli(args: list[str], timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["nmcli", *args], capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def _fields(line: str, count: int) -> list[str]:
    # nmcli -t escapes field separators; the values we show are simple enough.
    parts = line.split(":", count - 1)
    return parts + [""] * (count - len(parts))


class NetworkPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._device_rows: list[Gtk.Widget] = []
        self._vpn_rows: list[Gtk.Widget] = []
        self._active_names: set[str] = set()

        self._build()

    def _build(self) -> None:
        self._device_group = Adw.PreferencesGroup(title=t("Devices"))
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text(t("Refresh network state"))
        refresh.connect("clicked", lambda _b: self.refresh())
        self._device_group.set_header_suffix(refresh)
        self.add(self._device_group)

        self._vpn_group = Adw.PreferencesGroup(title=t("VPN connections"))
        self.add(self._vpn_group)

        self._build_hotspot()
        self._build_ipv4()
        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────

    def refresh(self) -> None:
        for row in self._device_rows:
            try:
                self._device_group.remove(row)
            except Exception:
                pass
        self._device_rows = []
        for row in self._vpn_rows:
            try:
                self._vpn_group.remove(row)
            except Exception:
                pass
        self._vpn_rows = []

        rc, active_out = _nmcli(["-t", "-f", "NAME", "connection", "show", "--active"])
        self._active_names = set(active_out.splitlines()) if rc == 0 else set()

        rc, devices = _nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])
        for line in devices.splitlines() if rc == 0 else []:
            name, type_, state, connection = _fields(line, 4)
            if type_ in ("loopback",):
                continue
            row = Adw.ActionRow(
                title=f"{name}  ·  {type_}",
                subtitle=f"{state}  ·  {connection or t('not connected')}",
            )
            connected = state == "connected"
            button = Gtk.Button(label=t("Disconnect") if connected else t("Connect"))
            button.set_valign(Gtk.Align.CENTER)
            button.connect(
                "clicked",
                lambda _b, n=name, c=connected: self._device_action(n, c),
            )
            row.add_suffix(button)
            self._device_group.add(row)
            self._device_rows.append(row)

        if not self._device_rows:
            row = Adw.ActionRow(title=t("No NetworkManager devices found"))
            self._device_group.add(row)
            self._device_rows.append(row)

        rc, connections = _nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])
        for line in connections.splitlines() if rc == 0 else []:
            name, type_ = _fields(line, 2)
            if type_ not in ("vpn", "wireguard"):
                continue
            active = name in self._active_names
            row = Adw.ActionRow(title=name, subtitle=f"{type_}  ·  {t('connected') if active else t('disconnected')}")
            button = Gtk.Button(label=t("Disconnect") if active else t("Connect"))
            button.set_valign(Gtk.Align.CENTER)
            button.connect("clicked", lambda _b, n=name, a=active: self._vpn_action(n, a))
            row.add_suffix(button)
            self._vpn_group.add(row)
            self._vpn_rows.append(row)

        if not self._vpn_rows:
            row = Adw.ActionRow(title=t("No VPN connections"), subtitle=t("Create one with nmcli or your VPN client"))
            self._vpn_group.add(row)
            self._vpn_rows.append(row)

        self._refresh_ipv4_choices()

    def _device_action(self, device: str, connected: bool) -> None:
        rc, out = _nmcli(["device", "disconnect" if connected else "connect", device])
        self.main_window.add_toast(Adw.Toast.new(
            t("Network device updated") if rc == 0 else t("Failed: {error}").format(error=out.splitlines()[0] if out else t("unknown error"))
        ))
        self.refresh()

    def _vpn_action(self, name: str, active: bool) -> None:
        rc, out = _nmcli(["connection", "down" if active else "up", name], timeout=30)
        self.main_window.add_toast(Adw.Toast.new(
            t("VPN updated") if rc == 0 else t("Failed: {error}").format(error=out.splitlines()[0] if out else t("unknown error"))
        ))
        self.refresh()

    # ── Hotspot ───────────────────────────────────────────────────────────

    def _build_hotspot(self) -> None:
        group = Adw.PreferencesGroup(
            title=t("Wi-Fi hotspot"),
            description=t("Share the current internet connection over Wi-Fi."),
        )
        self._hotspot_ssid = Adw.EntryRow(title=t("Network name"))
        self._hotspot_ssid.set_text("Caelestia Hotspot")
        group.add(self._hotspot_ssid)
        self._hotspot_password = Adw.PasswordEntryRow(title=t("Password (at least 8 characters)"))
        group.add(self._hotspot_password)

        row = Adw.ActionRow(title=t("Hotspot control"))
        start = Gtk.Button(label=t("Start"))
        start.add_css_class("suggested-action")
        start.connect("clicked", lambda _b: self._hotspot_start())
        stop = Gtk.Button(label=t("Stop"))
        stop.connect("clicked", lambda _b: self._hotspot_stop())
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.append(start)
        box.append(stop)
        row.add_suffix(box)
        group.add(row)
        self.add(group)

    def _wifi_device(self) -> str:
        rc, out = _nmcli(["-t", "-f", "DEVICE,TYPE", "device"])
        for line in out.splitlines() if rc == 0 else []:
            name, type_ = _fields(line, 2)
            if type_ == "wifi":
                return name
        return ""

    def _hotspot_start(self) -> None:
        device = self._wifi_device()
        ssid = self._hotspot_ssid.get_text().strip()
        password = self._hotspot_password.get_text()
        if not device:
            self.main_window.add_toast(Adw.Toast.new(t("No Wi-Fi device found")))
            return
        if len(password) < 8:
            self.main_window.add_toast(Adw.Toast.new(t("Hotspot password must be at least 8 characters")))
            return
        rc, out = _nmcli(
            ["device", "wifi", "hotspot", "ifname", device, "ssid", ssid, "password", password],
            timeout=30,
        )
        self.main_window.add_toast(Adw.Toast.new(
            t("Hotspot started") if rc == 0 else t("Hotspot failed: {error}").format(error=out.splitlines()[0] if out else t("unknown error"))
        ))
        self.refresh()

    def _hotspot_stop(self) -> None:
        rc, out = _nmcli(["connection", "down", "Hotspot"], timeout=15)
        self.main_window.add_toast(Adw.Toast.new(
            t("Hotspot stopped") if rc == 0 else t("No active hotspot found")
        ))
        self.refresh()

    # ── IPv4 ──────────────────────────────────────────────────────────────

    def _build_ipv4(self) -> None:
        self._ipv4_group = Adw.PreferencesGroup(
            title=t("IPv4 (active connection)"),
            description=t("Changing these values can disconnect you. Existing values are shown for reference."),
        )
        chooser = Adw.ActionRow(title=t("Connection"))
        self._ipv4_combo = Gtk.ComboBoxText()
        self._ipv4_combo.set_valign(Gtk.Align.CENTER)
        self._ipv4_combo.connect("changed", lambda _c: self._load_ipv4())
        chooser.add_suffix(self._ipv4_combo)
        self._ipv4_group.add(chooser)

        self._ipv4_method = Adw.EntryRow(title=t("Method (auto / manual)"))
        self._ipv4_group.add(self._ipv4_method)
        self._ipv4_address = Adw.EntryRow(title=t("Addresses (CIDR, comma-separated)"))
        self._ipv4_group.add(self._ipv4_address)
        self._ipv4_gateway = Adw.EntryRow(title=t("Gateway"))
        self._ipv4_group.add(self._ipv4_gateway)
        self._ipv4_dns = Adw.EntryRow(title=t("DNS servers (comma-separated)"))
        self._ipv4_group.add(self._ipv4_dns)

        apply_row = Adw.ActionRow(title=t("Apply IPv4 settings"))
        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", lambda _b: self._apply_ipv4())
        apply_row.add_suffix(apply_btn)
        self._ipv4_group.add(apply_row)
        self.add(self._ipv4_group)
        self._ipv4_values: dict[str, str] = {}

    def _refresh_ipv4_choices(self) -> None:
        current = self._ipv4_combo.get_active_id()
        self._ipv4_combo.remove_all()
        for name in sorted(self._active_names):
            self._ipv4_combo.append(name, name)
        if current and self._ipv4_combo.set_active_id(current):
            pass
        else:
            self._ipv4_combo.set_active(0)
        self._load_ipv4()

    def _load_ipv4(self) -> None:
        name = self._ipv4_combo.get_active_id()
        if not name:
            return
        rc, out = _nmcli(
            ["-t", "-f", "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns",
             "connection", "show", name]
        )
        values: dict[str, str] = {}
        if rc == 0:
            for line in out.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    values[key.strip()] = value.strip()
        self._ipv4_method.set_text(values.get("ipv4.method", ""))
        self._ipv4_address.set_text(values.get("ipv4.addresses", "").replace("\\,", ",").replace("\\:", ":"))
        self._ipv4_gateway.set_text(values.get("ipv4.gateway", ""))
        self._ipv4_dns.set_text(values.get("ipv4.dns", "").replace("\\,", ","))

    def _apply_ipv4(self) -> None:
        name = self._ipv4_combo.get_active_id()
        if not name:
            return
        dialog = Adw.AlertDialog(
            heading=t("Apply IPv4 settings?"),
            body=t("This will modify and reactivate “{name}”. You may lose connectivity.").format(name=name),
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("apply", t("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_dialog, response: str) -> None:
            if response != "apply":
                return
            args = ["connection", "modify", name]
            method = self._ipv4_method.get_text().strip() or "auto"
            args += ["ipv4.method", method]
            if method == "manual":
                if self._ipv4_address.get_text().strip():
                    args += ["ipv4.addresses", self._ipv4_address.get_text().strip()]
                if self._ipv4_gateway.get_text().strip():
                    args += ["ipv4.gateway", self._ipv4_gateway.get_text().strip()]
            if self._ipv4_dns.get_text().strip():
                args += ["ipv4.dns", self._ipv4_dns.get_text().strip()]
            rc, out = _nmcli(args, timeout=15)
            if rc == 0:
                _nmcli(["connection", "up", name], timeout=30)
            self.main_window.add_toast(Adw.Toast.new(
                t("IPv4 settings applied") if rc == 0 else t("Failed: {error}").format(error=out.splitlines()[0] if out else t("unknown error"))
            ))
            self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
