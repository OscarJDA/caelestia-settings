"""Backlight, night light and external monitor brightness (D3)."""

from __future__ import annotations

import os
import re
import signal
import shutil
import subprocess
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.config import HYPR_EXECS_CONF, HYPR_INCLUDES_DIR, hyprctl_reload, is_lua_mode
from src.safe_io import atomic_write_json, atomic_write_text, read_json
from src.lang import t  # noqa: E402

SETTINGS_FILE = Path.home() / ".config" / "caelestia-settings" / "display.json"
BACKLIGHT = Path("/sys/class/backlight")
EXECS_LUA = HYPR_INCLUDES_DIR / "execs.lua"
NIGHT_MARKER = "caelestia-settings: night-light"


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return default


class DisplayPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._night_process: subprocess.Popen | None = None
        self._timers: dict[str, int] = {}
        self._ddc_rows: list[Gtk.Widget] = []

        self._backlight_group = Adw.PreferencesGroup(title=t("Backlight"))
        self.add(self._backlight_group)
        self._build_backlight()

        self._night_group = Adw.PreferencesGroup(
            title=t("Night light"),
            description=t("Requires gammastep. The effect lasts until this app stops it or you log out."),
        )
        self.add(self._night_group)
        self._build_night_light()

        self._ddc_group = Adw.PreferencesGroup(
            title=t("External monitors (DDC/CI)"),
            description=t("ddcutil must be installed and the i2c device accessible."),
        )
        self.add(self._ddc_group)
        self._build_ddc()

    # ── Backlight ─────────────────────────────────────────────────────────

    def _build_backlight(self) -> None:
        devices = sorted(path.name for path in BACKLIGHT.glob("*")) if BACKLIGHT.exists() else []
        if not devices:
            self._backlight_group.add(Adw.ActionRow(title=t("No backlight device found")))
            return
        if not shutil.which("brightnessctl"):
            self._backlight_group.add(
                Adw.ActionRow(title=t("brightnessctl not installed"), subtitle="sudo pacman -S brightnessctl")
            )
            return

        for device in devices:
            base = BACKLIGHT / device
            maximum = max(1, _read_int(base / "max_brightness", 100))
            current = _read_int(base / "brightness", maximum)
            percent = round(current / maximum * 100)
            row = Adw.ActionRow(title=device, subtitle=f"{percent}%")
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
            scale.set_hexpand(True)
            scale.set_draw_value(True)
            scale.set_size_request(220, -1)
            scale.set_value(percent)
            scale.connect("value-changed", self._on_brightness, device, row)
            row.add_suffix(scale)
            self._backlight_group.add(row)

    def _on_brightness(self, scale, device: str, row: Adw.ActionRow) -> None:
        value = int(scale.get_value())
        row.set_subtitle(f"{value}%")
        key = f"brightness:{device}"
        timer = self._timers.pop(key, None)
        if timer:
            GLib.source_remove(timer)

        def apply() -> bool:
            self._timers.pop(key, None)
            subprocess.run(
                ["brightnessctl", "-q", "-d", device, "set", f"{value}%"],
                capture_output=True,
                timeout=3,
            )
            return False

        self._timers[key] = GLib.timeout_add(120, apply)

    # ── Night light ───────────────────────────────────────────────────────

    def _build_night_light(self) -> None:
        self._night_settings = read_json(SETTINGS_FILE, {})
        self._loading_night = False
        self._night_temp_timer = 0
        self._gamma_reset_running = False
        self._gamma_reset_process: subprocess.Popen | None = None
        running = bool(self._gammastep_pids())

        self._night_enabled = Adw.SwitchRow(
            title=t("Enable night light"),
            subtitle=t("Starts/stops gammastep and enables or disables its login autostart"),
        )
        self._night_enabled.set_active(
            bool(self._night_settings.get("nightLightEnabled", False)) or running
        )
        self._night_enabled.connect("notify::active", self._on_night_toggled)
        self._night_group.add(self._night_enabled)

        row = Adw.ActionRow(title=t("Temperature"), subtitle=t("Kelvin — lower is warmer"))
        self._night_temp = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1000, 6500, 100)
        self._night_temp.set_draw_value(True)
        self._night_temp.set_hexpand(True)
        self._night_temp.set_size_request(240, -1)
        self._night_temp.set_value(float(self._night_settings.get("nightTemperature", 4000)))
        self._night_temp.connect("value-changed", self._on_night_temp)
        row.add_suffix(self._night_temp)
        self._night_group.add(row)

        self._night_status = Adw.ActionRow(title=t("Status"), subtitle=t("Checking…"))
        self._night_group.add(self._night_status)

        self._night_autostart = Adw.SwitchRow(
            title=t("Start at login"),
            subtitle=t("Manages the gammastep line in execs.lua / execs.conf"),
        )
        self._night_autostart.set_active(self._autostart_active())
        self._night_autostart.connect("notify::active", self._on_night_autostart)
        self._night_group.add(self._night_autostart)

        force_row = Adw.ActionRow(
            title=t("Stop and reset gamma"),
            subtitle=t("Kills gammastep (including external autostart instances) and clears its gamma adjustment"),
        )
        force_btn = Gtk.Button(label=t("Stop now"))
        force_btn.add_css_class("destructive-action")
        force_btn.set_valign(Gtk.Align.CENTER)
        force_btn.connect("clicked", lambda _b: self._force_stop_night_light())
        force_row.add_suffix(force_btn)
        self._night_group.add(force_row)

        self._night_group.add(
            Adw.ActionRow(
                title=t("Still warm after stopping?"),
                subtitle=t("Log out or restart Hyprland to clear a stuck gamma LUT (Hyprland 0.56 can report gamma_size 0)."),
            )
        )

        if not shutil.which("gammastep"):
            self._night_group.add(
                Adw.ActionRow(
                    title=t("gammastep not installed"),
                    subtitle=t("Install gammastep to control the colour temperature"),
                )
            )
            self._night_enabled.set_sensitive(False)
            self._night_temp.set_sensitive(False)
            self._night_autostart.set_sensitive(False)
            force_btn.set_sensitive(False)
        elif self._night_enabled.get_active() and not running:
            GLib.idle_add(lambda: (self._start_night_light(), False)[1])
        self._update_night_status()

    def _gammastep_pids(self) -> list[int]:
        pids: list[int] = []
        proc_root = Path("/proc")
        try:
            candidates = list(proc_root.iterdir())
        except OSError:
            return pids
        for entry in candidates:
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / "status").read_text(encoding="utf-8", errors="ignore")
                if "\nState:\tZ" in status or status.startswith("State:\tZ"):
                    continue
                if (entry / "comm").read_text().strip() == "gammastep":
                    pids.append(int(entry.name))
            except OSError:
                continue
        return pids

    def _update_night_status(self, extra: str = "") -> None:
        if not shutil.which("gammastep"):
            self._night_status.set_subtitle(t("gammastep not installed"))
            return
        reset_pid = (
            self._gamma_reset_process.pid
            if self._gamma_reset_process is not None and self._gamma_reset_process.poll() is None
            else None
        )
        pids = [pid for pid in self._gammastep_pids() if pid != reset_pid]
        if (reset_pid is not None or self._gamma_reset_running) and not pids:
            base = t("Resetting gamma…")
        elif pids:
            base = t("Running (PID {pids})").format(pids=", ".join(str(pid) for pid in pids))
        else:
            base = t("Stopped")
        self._night_status.set_subtitle(f"{base}{' · ' + extra if extra else ''}")

    def _save_night_settings(self) -> None:
        self._night_settings["nightLightEnabled"] = self._night_enabled.get_active()
        self._night_settings["nightTemperature"] = int(self._night_temp.get_value())
        if hasattr(self, "_night_autostart"):
            self._night_settings["nightAutostart"] = self._night_autostart.get_active()
        atomic_write_json(SETTINGS_FILE, self._night_settings)

    def _on_night_temp(self, scale) -> None:
        self._save_night_settings()
        if not self._night_enabled.get_active() or not shutil.which("gammastep"):
            return
        if self._night_temp_timer:
            GLib.source_remove(self._night_temp_timer)
        self._night_temp_timer = GLib.timeout_add(400, self._apply_night_temp)

    def _apply_night_temp(self) -> bool:
        self._night_temp_timer = 0
        if self._night_enabled.get_active():
            self._start_night_light()
        return False

    def _toast(self, message: str) -> None:
        if self.main_window is not None:
            self.main_window.add_toast(Adw.Toast.new(message))

    def _on_night_toggled(self, row, _pspec) -> None:
        if self._loading_night:
            return
        self._save_night_settings()
        if row.get_active():
            self._start_night_light()
        else:
            # Turning night light off must also stop an autostart instance and
            # prevent it from coming back on the next login.
            self._set_autostart_ui(False)
            self._stop_night_light(reset=True)
            self._save_night_settings()
            self._toast(t("Night light stopped — resetting gamma…"))

    def _on_night_autostart(self, row, _pspec) -> None:
        if self._loading_night:
            return
        ok = self._set_autostart(row.get_active())
        self._save_night_settings()
        self._toast(
            t("Night light will start at login")
            if row.get_active() and ok
            else (t("Autostart disabled") if ok else t("Could not update the autostart file"))
        )

    def _set_autostart_ui(self, enabled: bool) -> None:
        if not hasattr(self, "_night_autostart"):
            return
        self._loading_night = True
        try:
            self._night_autostart.set_active(enabled)
        finally:
            self._loading_night = False
        self._set_autostart(enabled)

    def _autostart_target(self) -> Path:
        if is_lua_mode():
            return EXECS_LUA if EXECS_LUA.exists() else self._hypr_user_lua()
        return HYPR_EXECS_CONF

    def _lua_autostart_files(self) -> list[Path]:
        paths = [self._hypr_user_lua(), EXECS_LUA]
        unique: list[Path] = []
        for path in paths:
            if path not in unique and path.exists():
                unique.append(path)
        return unique or [EXECS_LUA]

    def _hypr_user_lua(self) -> Path:
        from src.config import CAELESTIA_HYPR_USER

        return CAELESTIA_HYPR_USER

    def _autostart_active(self) -> bool:
        if is_lua_mode():
            for path in self._lua_autostart_files():
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                if any(
                    re.match(r"^\s*hl\.exec_cmd\(.*gammastep.*\)", line)
                    for line in text.splitlines()
                ):
                    return True
            return False
        path = self._autostart_target()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False
        return any(
            re.match(r"^\s*exec(?:-once)?\s*=.*gammastep", line)
            for line in text.splitlines()
        )

    def _set_autostart(self, enabled: bool) -> bool:
        if is_lua_mode():
            return self._set_lua_autostart(enabled)
        return self._set_conf_autostart(enabled)

    def _set_lua_autostart(self, enabled: bool) -> bool:
        active = re.compile(r"^\s*(hl\.exec_cmd\(.*gammastep.*\))\s*$")
        commented = re.compile(r"^(\s*)--\s*(hl\.exec_cmd\(.*gammastep.*\))\s*$")
        files = self._lua_autostart_files()
        texts = {}
        for path in files:
            try:
                texts[path] = path.read_text(encoding="utf-8")
            except OSError:
                texts[path] = ""

        if not enabled:
            changed = False
            for path, text in texts.items():
                lines = text.splitlines()
                local = False
                for index, line in enumerate(lines):
                    if active.match(line):
                        lines[index] = "-- " + line.lstrip()
                        local = True
                if local:
                    texts[path] = "\n".join(lines) + "\n"
                    changed = True
            if changed:
                for path, text in texts.items():
                    if text != self._read_or_empty(path):
                        try:
                            atomic_write_text(path, text)
                        except OSError as exc:
                            print(f"Could not update {path}: {exc}")
                            return False
                hyprctl_reload()
            self._update_night_status()
            return True

        # Already active anywhere?
        for text in texts.values():
            if any(active.match(line) for line in text.splitlines()):
                self._update_night_status()
                return True

        # Uncomment the first commented executable gammastep line.
        for path, text in texts.items():
            lines = text.splitlines()
            for index, line in enumerate(lines):
                match = commented.match(line)
                if match:
                    lines[index] = match.group(1) + match.group(2)
                    try:
                        atomic_write_text(path, "\n".join(lines) + "\n")
                        hyprctl_reload()
                        self._update_night_status()
                        return True
                    except OSError as exc:
                        print(f"Could not update {path}: {exc}")
                        return False

        target = EXECS_LUA if EXECS_LUA.exists() else self._hypr_user_lua()
        try:
            text = self._read_or_empty(target)
            text = text.rstrip() + "\n\n" + f"-- {NIGHT_MARKER}\n" + 'hl.exec_cmd("sleep 1 && gammastep")\n'
            atomic_write_text(target, text)
            hyprctl_reload()
        except OSError as exc:
            print(f"Could not update {target}: {exc}")
            return False
        self._update_night_status()
        return True

    @staticmethod
    def _read_or_empty(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _set_conf_autostart(self, enabled: bool) -> bool:
        path = self._autostart_target()
        try:
            text = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            text = ""
        lines = text.splitlines()
        active = re.compile(r"^\s*(exec(?:-once)?\s*=.*gammastep.*)$")
        commented = re.compile(r"^(\s*)#\s*(exec(?:-once)?\s*=.*gammastep.*)$")
        changed = False
        if enabled:
            for index, line in enumerate(lines):
                match = commented.match(line)
                if match:
                    lines[index] = match.group(1) + match.group(2)
                    changed = True
                    break
            if not any(active.match(line) for line in lines):
                lines.extend(["", f"exec-once = gammastep  # {NIGHT_MARKER}"])
                changed = True
        else:
            for index, line in enumerate(lines):
                if active.match(line):
                    lines[index] = "# " + line.lstrip()
                    changed = True
        if changed:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_text(path, "\n".join(lines) + "\n")
                hyprctl_reload()
            except OSError as exc:
                print(f"Could not update night light autostart: {exc}")
                return False
        self._update_night_status()
        return True

    def _start_night_light(self) -> None:
        if not shutil.which("gammastep"):
            return
        # Kill any externally started instance first (autostart, shell, etc.).
        self._stop_night_light(reset=False)
        temperature = int(self._night_temp.get_value())
        try:
            self._night_process = subprocess.Popen(
                ["gammastep", "-P", "-O", str(temperature)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            print(f"gammastep failed: {exc}")
            self._night_process = None
        GLib.timeout_add(300, lambda: (self._update_night_status(), False)[1])

    def _stop_night_light(self, reset: bool = True) -> tuple[bool, str]:
        # Cancel an in-flight gamma reset before killing the daemon processes.
        if self._gamma_reset_process is not None and self._gamma_reset_process.poll() is None:
            try:
                self._gamma_reset_process.terminate()
            except OSError:
                pass
        self._gamma_reset_process = None

        pids = set(self._gammastep_pids())
        if self._night_process is not None and self._night_process.poll() is None:
            pids.add(self._night_process.pid)

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        for _ in range(20):
            if not self._gammastep_pids():
                break
            time.sleep(0.05)
        for pid in self._gammastep_pids():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if self._night_process is not None:
            try:
                self._night_process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self._night_process = None

        if reset:
            self._reset_gamma_async()
        self._update_night_status()
        return True, ""

    def _reset_gamma_async(self) -> None:
        if self._gamma_reset_running:
            return
        self._gamma_reset_running = True
        self._update_night_status()

        def worker() -> None:
            ok, message = self._reset_gamma()
            GLib.idle_add(self._on_gamma_reset, ok, message)

        threading.Thread(target=worker, daemon=True).start()

    def _on_gamma_reset(self, ok: bool, message: str) -> bool:
        self._gamma_reset_running = False
        if ok:
            self._update_night_status(t("gamma reset"))
        else:
            self._update_night_status(t("gamma reset failed"))
            self._toast(
                t("Gamma reset failed (Hyprland may report gamma_size 0). Log out or restart Hyprland.")
            )
            print(f"Gamma reset failed: {message}")
        return False

    def _reset_gamma(self) -> tuple[bool, str]:
        if not shutil.which("gammastep"):
            return False, "gammastep not installed"
        try:
            process = subprocess.Popen(
                ["gammastep", "-x"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            return False, str(exc)
        self._gamma_reset_process = process
        try:
            try:
                stdout, stderr = process.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                return False, "gammastep -x timed out"
        finally:
            self._gamma_reset_process = None
        output = ((stdout or "") + (stderr or "")).strip()
        if process.returncode == 0:
            return True, output
        return False, output or f"gammastep -x exited with {process.returncode}"

    def _force_stop_night_light(self) -> None:
        self._loading_night = True
        try:
            self._night_enabled.set_active(False)
            self._night_autostart.set_active(False)
        finally:
            self._loading_night = False
        self._save_night_settings()
        self._set_autostart(False)
        self._stop_night_light(reset=True)
        self._toast(t("gammastep stopped — resetting gamma…"))

    # ── DDC/CI ────────────────────────────────────────────────────────────


    def _build_ddc(self) -> None:
        scan = Adw.ActionRow(title=t("Scan for DDC/CI monitors"), subtitle=t("ddcutil may take several seconds"))
        button = Gtk.Button(label=t("Scan"))
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: self._scan_ddc())
        scan.add_suffix(button)
        self._ddc_group.add(scan)
        self._ddc_scan_row = scan
        if not shutil.which("ddcutil"):
            scan.set_subtitle(t("ddcutil not installed"))

    def _scan_ddc(self) -> None:
        if not shutil.which("ddcutil"):
            return
        self._ddc_scan_row.set_subtitle(t("Scanning…"))
        for row in self._ddc_rows:
            self._ddc_group.remove(row)
        self._ddc_rows = []

        def worker() -> None:
            try:
                result = subprocess.run(
                    ["ddcutil", "detect"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                lines = result.stdout.splitlines()
            except (OSError, subprocess.TimeoutExpired):
                lines = []
            displays = []
            current = None
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("Display "):
                    current = {"n": stripped.split()[1].rstrip(":")}
                    displays.append(current)
                elif stripped.startswith("Invalid display"):
                    current = None
                elif current is not None and stripped.startswith("Monitor:"):
                    current["name"] = stripped.split(":", 1)[1].strip()
            GLib.idle_add(self._apply_ddc, displays)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ddc(self, displays: list[dict]) -> bool:
        self._ddc_scan_row.set_subtitle(
            t("{count} display(s) found").format(count=len(displays)) if displays else t("No DDC/CI displays found")
        )
        for display in displays:
            number = display.get("n")
            if not number:
                continue
            row = Adw.ActionRow(title=display.get("name") or t("Display {number}").format(number=number))
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            scale.set_hexpand(True)
            scale.set_draw_value(True)
            scale.set_size_request(220, -1)
            scale.set_value(50)
            scale.connect("value-changed", self._on_ddc_brightness, number, row)
            row.add_suffix(scale)
            self._ddc_group.add(row)
            self._ddc_rows.append(row)
        return False

    def _on_ddc_brightness(self, scale, number: str, row: Adw.ActionRow) -> None:
        value = int(scale.get_value())
        row.set_subtitle(f"{value}%")
        key = f"ddc:{number}"
        timer = self._timers.pop(key, None)
        if timer:
            GLib.source_remove(timer)

        def apply() -> bool:
            self._timers.pop(key, None)
            subprocess.run(
                ["ddcutil", "--display", number, "setvcp", "10", str(value)],
                capture_output=True,
                timeout=10,
            )
            return False

        self._timers[key] = GLib.timeout_add(600, apply)
