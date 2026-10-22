"""Bluetooth device management (BlueZ via bluetoothctl).

The page never blocks the UI: every ``bluetoothctl`` call that can take a
while runs in a worker thread and reports back through ``GLib.idle_add``.
"""

from __future__ import annotations

import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.lang import t  # noqa: E402

SCAN_SECONDS = 20


class BluetoothPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._refreshing = False
        self._scan_timeout = None
        self._scan_elapsed = 0
        self._device_rows: list[Gtk.Widget] = []
        self._available = shutil.which("bluetoothctl") is not None

        adapter_group = Adw.PreferencesGroup(
            title=t("Adapter"),
            description=t("BlueZ adapter state and device discovery."),
        )
        self.power_row = Adw.SwitchRow(
            title=t("Bluetooth"),
            subtitle=t("Power the adapter on or off"),
        )
        self.power_row.set_sensitive(self._available)
        self.power_row.connect("notify::active", self._on_power_toggled)
        adapter_group.add(self.power_row)

        self.scan_row = Adw.SwitchRow(
            title=t("Scan for devices"),
            subtitle=t("Discover nearby devices for {seconds} seconds").format(seconds=SCAN_SECONDS),
        )
        self.scan_row.set_sensitive(False)
        self.scan_row.connect("notify::active", self._on_scan_toggled)
        adapter_group.add(self.scan_row)
        self.add(adapter_group)

        self.devices_group = Adw.PreferencesGroup(title=t("Devices"))
        self.add(self.devices_group)

        self.status_row = Adw.ActionRow(
            title=t("Bluetooth is unavailable"),
            subtitle=t("Install bluez and make sure the bluetooth service is running."),
        )
        self.devices_group.add(self.status_row)
        self._status_attached = True

        self._refresh_async()

    # ── bluetoothctl helpers ──────────────────────────────────────────────

    def _run(self, args: list[str], timeout: int = 20):
        try:
            return subprocess.run(
                ["bluetoothctl", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"bluetoothctl {' '.join(args)} failed: {exc}")
            return None

    def _toast(self, message: str) -> None:
        if hasattr(self.main_window, "add_toast"):
            self.main_window.add_toast(Adw.Toast.new(message))

    # ── State collection ──────────────────────────────────────────────────

    def _refresh_async(self) -> None:
        if not self._available or self._refreshing:
            return
        self._refreshing = True
        threading.Thread(target=self._collect_state, daemon=True).start()

    def _collect_state(self) -> None:
        powered = False
        discovering = False
        devices: list[dict] = []
        result = self._run(["show"], timeout=10)
        if result is None:
            GLib.idle_add(self._apply_state, False, [], False, "Adapter not available")
            return
        rc, out, err = result.returncode, result.stdout, result.stderr
        if rc != 0 and not out:
            GLib.idle_add(self._apply_state, False, [], False, err or "Adapter not available")
            return
        for line in out.splitlines():
            if line.strip().startswith("Powered:"):
                powered = line.split(":", 1)[1].strip().lower() == "yes"
            elif line.strip().startswith("Discovering:"):
                discovering = line.split(":", 1)[1].strip().lower() == "yes"

        if powered:
            result = self._run(["devices"], timeout=10)
            device_lines = result.stdout.splitlines() if result is not None else []
            for line in device_lines:
                if not line.startswith("Device "):
                    continue
                parts = line.split(" ", 2)
                if len(parts) < 2:
                    continue
                mac = parts[1]
                name = parts[2] if len(parts) > 2 else ""
                info = self._device_info(mac)
                devices.append(
                    {
                        "mac": mac,
                        "name": name or info.get("Name", mac),
                        "alias": info.get("Alias") or name or mac,
                        "paired": info.get("Paired", "no").lower() == "yes",
                        "trusted": info.get("Trusted", "no").lower() == "yes",
                        "connected": info.get("Connected", "no").lower() == "yes",
                    }
                )
        devices.sort(key=lambda d: (not d["connected"], d["alias"].lower()))
        GLib.idle_add(self._apply_state, powered, devices, discovering, "")

    def _device_info(self, mac: str) -> dict:
        result = self._run(["info", mac], timeout=10)
        info: dict[str, str] = {}
        if result is not None and result.returncode == 0:
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    info[key.strip()] = value.strip()
        return info

    # ── UI refresh ────────────────────────────────────────────────────────

    def _apply_state(self, powered: bool, devices: list[dict], discovering: bool, error: str) -> bool:
        self._refreshing = False
        self.power_row.handler_block_by_func(self._on_power_toggled)
        self.power_row.set_active(powered)
        self.power_row.handler_unblock_by_func(self._on_power_toggled)
        self.scan_row.set_sensitive(powered)

        self.scan_row.handler_block_by_func(self._on_scan_toggled)
        self.scan_row.set_active(discovering)
        self.scan_row.handler_unblock_by_func(self._on_scan_toggled)

        for row in self._device_rows:
            self.devices_group.remove(row)
        self._device_rows = []

        if error and not devices:
            if not self._status_attached:
                self.devices_group.add(self.status_row)
                self._status_attached = True
            self.status_row.set_title(t("Bluetooth is unavailable"))
            self.status_row.set_subtitle(error)
            return False

        if self._status_attached:
            self.devices_group.remove(self.status_row)
            self._status_attached = False

        if not powered:
            row = Adw.ActionRow(
                title=t("Bluetooth is off"),
                subtitle=t("Turn the adapter on to see nearby devices."),
            )
            self.devices_group.add(row)
            self._device_rows.append(row)
            return False

        if not devices:
            row = Adw.ActionRow(
                title=t("No devices"),
                subtitle=t("Start a scan to discover nearby devices."),
            )
            self.devices_group.add(row)
            self._device_rows.append(row)
            return False

        for device in devices:
            row = self._make_device_row(device)
            self.devices_group.add(row)
            self._device_rows.append(row)
        return False

    def _make_device_row(self, device: dict) -> Adw.ActionRow:
        state = t("Connected") if device["connected"] else (t("Paired") if device["paired"] else t("Available"))
        row = Adw.ActionRow(
            title=device["alias"],
            subtitle=f"{device['mac']}  ·  {state}",
        )

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_valign(Gtk.Align.CENTER)

        if device["connected"]:
            connect = Gtk.Button(label=t("Disconnect"))
            connect.connect("clicked", lambda _b: self._action(["disconnect", device["mac"]], t("Disconnected")))
        else:
            connect = Gtk.Button(label=t("Connect"))
            connect.add_css_class("suggested-action")
            connect.connect("clicked", lambda _b: self._action(["connect", device["mac"]], t("Connecting")))
        connect.add_css_class("flat")
        box.append(connect)

        if not device["paired"]:
            pair = Gtk.Button(label=t("Pair"))
            pair.add_css_class("flat")
            pair.connect("clicked", lambda _b: self._action(["pair", device["mac"]], t("Pairing")))
            box.append(pair)

        trust = Gtk.Button(
            icon_name="security-high-symbolic" if device["trusted"] else "security-low-symbolic"
        )
        trust.set_tooltip_text(t("Untrust device") if device["trusted"] else t("Trust device"))
        trust.add_css_class("flat")
        trust.connect(
            "clicked",
            lambda _b: self._action(
                ["untrust" if device["trusted"] else "trust", device["mac"]],
                t("Device updated"),
            ),
        )
        box.append(trust)

        forget = Gtk.Button(icon_name="user-trash-symbolic")
        forget.set_tooltip_text(t("Forget device"))
        forget.add_css_class("flat")
        forget.connect("clicked", lambda _b: self._confirm_forget(device))
        box.append(forget)

        row.add_suffix(box)
        row.set_activatable(False)
        return row

    # ── Actions ───────────────────────────────────────────────────────────

    def _action(self, args: list[str], success: str) -> None:
        def worker() -> None:
            result = self._run(args, timeout=30)
            ok = result is not None and result.returncode == 0
            message = success if ok else t("Bluetooth action failed: {args}").format(args=" ".join(args))
            if not ok and result is not None:
                message = (result.stderr or result.stdout or message).strip().splitlines()[0]
            GLib.idle_add(self._after_action, message, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _after_action(self, message: str, ok: bool) -> bool:
        self._toast(message)
        self._refresh_async()
        return False

    def _confirm_forget(self, device: dict) -> None:
        dialog = Adw.AlertDialog(
            heading=t("Forget device?"),
            body=t("{name} ({mac}) will be removed from the list.").format(name=device["alias"], mac=device["mac"]),
        )
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("forget", t("Forget"))
        dialog.set_response_appearance("forget", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response: str) -> None:
            if response == "forget":
                self._action(["remove", device["mac"]], t("Device forgotten"))

        dialog.connect("response", on_response)
        dialog.present(self.get_root())

    def _on_power_toggled(self, row, _pspec) -> None:
        if not self._available or self._refreshing:
            return
        if not row.get_active():
            self._stop_scan()
        self._action(["power", "on" if row.get_active() else "off"], t("Bluetooth updated"))

    def _on_scan_toggled(self, row, _pspec) -> None:
        if not self._available or self._refreshing:
            return
        if row.get_active():
            self._start_scan()
        else:
            self._stop_scan()

    def _start_scan(self) -> None:
        self._scan_elapsed = 0
        self._action(["scan", "on"], "Scanning for devices")
        if self._scan_timeout:
            GLib.source_remove(self._scan_timeout)
        self._scan_timeout = GLib.timeout_add_seconds(2, self._scan_tick)

    def _scan_tick(self) -> bool:
        self._scan_elapsed += 2
        self._refresh_async()
        if self._scan_elapsed >= SCAN_SECONDS:
            self._stop_scan()
            return False
        return True

    def _stop_scan(self) -> None:
        if self._scan_timeout:
            GLib.source_remove(self._scan_timeout)
            self._scan_timeout = None
        self._action(["scan", "off"], "Scan stopped")
        self.scan_row.handler_block_by_func(self._on_scan_toggled)
        self.scan_row.set_active(False)
        self.scan_row.handler_unblock_by_func(self._on_scan_toggled)
