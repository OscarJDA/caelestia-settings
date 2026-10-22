import os
import shlex
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from gi.repository import Gtk, Adw, GLib
from src.lang import t
from src.safe_io import atomic_write_json, read_json

try:
    import psutil as _psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    import warnings as _warnings
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", FutureWarning)
        import pynvml as _nvml
    _HAS_NVML = True
except ImportError:
    _HAS_NVML = False

import caelestia_core

_HWMON = Path("/sys/class/hwmon")
_CPU_TEMP_KEYS = ["k10temp", "coretemp", "cpu_thermal", "nct6798"]
_FANS_SETTINGS = Path.home() / ".config" / "caelestia-settings" / "fans.json"


# ── Hardware readers ──────────────────────────────────────────────────────────

def read_cpu_temp() -> int | None:
    if not _HAS_PSUTIL:
        return None
    try:
        temps = _psutil.sensors_temperatures()
        for key in _CPU_TEMP_KEYS:
            if key in temps and temps[key]:
                return int(temps[key][0].current)
    except Exception:
        pass
    return None


def _read_sys_fans() -> list[dict]:
    if not _HAS_PSUTIL:
        return []
    try:
        result = []
        for chip, entries in _psutil.sensors_fans().items():
            for e in entries:
                result.append({"label": e.label or chip, "rpm": e.current})
        return result
    except Exception:
        return []


def read_gpu_stats() -> dict | None:
    if not _HAS_NVML:
        return None
    try:
        _nvml.nvmlInit()
        h = _nvml.nvmlDeviceGetHandleByIndex(0)
        temp = _nvml.nvmlDeviceGetTemperature(h, _nvml.NVML_TEMPERATURE_GPU)
        try:
            fan = _nvml.nvmlDeviceGetFanSpeed(h)
        except _nvml.NVMLError:
            fan = None
        return {"temp": temp, "fan_pct": fan}
    except Exception:
        return None
    finally:
        try:
            _nvml.nvmlShutdown()
        except Exception:
            pass


def _set_gpu_fan(speed: int) -> str | None:
    if not _HAS_NVML:
        return "pynvml not installed"
    try:
        _nvml.nvmlInit()
        h = _nvml.nvmlDeviceGetHandleByIndex(0)
        _nvml.nvmlDeviceSetFanSpeed_v2(h, 0, max(0, min(100, speed)))
        return None
    except _nvml.NVMLError_NoPermission:
        return t("GPU fan: enable Coolbits — sudo nvidia-xconfig --cool-bits=4")
    except _nvml.NVMLError_NotSupported:
        return t("GPU fan: manual control not supported (Zero-RPM mode?)")
    except Exception as e:
        return str(e)
    finally:
        try:
            _nvml.nvmlShutdown()
        except Exception:
            pass


# ── Hwmon / system fan PWM ────────────────────────────────────────────────────

def _find_pwm_channels() -> list[dict]:
    channels = []
    try:
        for hwmon in sorted(_HWMON.iterdir()):
            name_file = hwmon / "name"
            if not name_file.exists():
                continue
            chip = name_file.read_text().strip()
            for i in range(1, 8):
                pwm = hwmon / f"pwm{i}"
                if not pwm.exists():
                    continue
                enable = hwmon / f"pwm{i}_enable"
                fan_rpm_file = hwmon / f"fan{i}_input"
                try:
                    cur_pct = caelestia_core.pwm_raw_to_percent(int(pwm.read_text()))
                except Exception:
                    cur_pct = 50
                channels.append({
                    "label":       f"{chip} — pwm{i}",
                    "pwm":         pwm,
                    "enable":      enable,
                    "fan_rpm":     fan_rpm_file if fan_rpm_file.exists() else None,
                    "current_pct": cur_pct,
                })
    except Exception:
        pass
    return channels


# ── Page ──────────────────────────────────────────────────────────────────────

class FansPage(Gtk.Box):
    def __init__(self, win, **kwargs):
        super().__init__(**kwargs)
        self.main_window = win
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._polling  = True
        self._auto_mode = False
        self._last_gpu_speed: int | None = None
        self._last_gpu_temp: int | None = None
        self._fan_rows: dict = {}
        self._settings = read_json(_FANS_SETTINGS, {})
        self._curve = self._settings.get("curve", {
            "t1": 50, "s1": 30, "t2": 72, "s2": 60, "t3": 80, "s3": 90, "hysteresis": 3,
        })

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.append(scroll)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12); box.set_margin_bottom(12)
        box.set_margin_start(12); box.set_margin_end(12)
        scroll.set_child(box)

        # ── Stats ────────────────────────────────────────────────────────
        self._stats_group = Adw.PreferencesGroup(title=GLib.markup_escape_text(t("Fan & Temperature")))
        box.append(self._stats_group)

        self._cpu_row = Adw.ActionRow(title="CPU")
        self._cpu_val = Gtk.Label(label="--")
        self._cpu_val.add_css_class("dim-label")
        self._cpu_row.add_suffix(self._cpu_val)
        self._stats_group.add(self._cpu_row)

        self._gpu_stat_row = Adw.ActionRow(title="GPU")
        self._gpu_stat_val = Gtk.Label(label="--")
        self._gpu_stat_val.add_css_class("dim-label")
        self._gpu_stat_row.add_suffix(self._gpu_stat_val)
        self._stats_group.add(self._gpu_stat_row)

        

        if not _HAS_PSUTIL:
            self._stats_group.add(Adw.ActionRow(
                title=t("python-psutil not installed"),
                subtitle="sudo pacman -S python-psutil"
            ))

        # ── GPU fan control ──────────────────────────────────────────────
        gpu_group = Adw.PreferencesGroup(title=t("GPU Fan Control"))
        box.append(gpu_group)

        if _HAS_NVML:
            self._auto_row = Adw.SwitchRow(
                title=t("Auto Fan Curve"),
                subtitle=GLib.markup_escape_text("30% < 50 °C  |  60% < 72 °C  |  90% ≥ 72 °C")
            )
            self._auto_row.connect("notify::active", self._on_auto_toggled)
            gpu_group.add(self._auto_row)

            slider_row = Adw.ActionRow(title=t("Fan Speed"))
            self._gpu_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
            self._gpu_slider.set_value(50)
            self._gpu_slider.set_hexpand(True)
            self._gpu_slider.set_draw_value(True)
            self._gpu_slider.connect("value-changed", self._on_gpu_slider)
            slider_row.add_suffix(self._gpu_slider)
            gpu_group.add(slider_row)

            preset_row = Adw.ActionRow(title=t("Presets"))
            pbox = Gtk.Box(spacing=6)
            pbox.set_valign(Gtk.Align.CENTER)
            for p in [25, 50, 75, 100]:
                btn = Gtk.Button(label=f"{p}%")
                btn.add_css_class("pill")
                btn.connect("clicked", lambda _, v=p: self._apply_gpu_speed(v))
                pbox.append(btn)
            preset_row.add_suffix(pbox)
            gpu_group.add(preset_row)

            curve_group = Adw.PreferencesGroup(
                title=t("Custom auto curve"),
                description=t("GPU temperature thresholds and fan speeds"),
            )
            box.append(curve_group)
            self._curve_rows = {}
            for key, label, is_temp in (
                ("t1", "Threshold 1", True),
                ("s1", "Speed 1", False),
                ("t2", "Threshold 2", True),
                ("s2", "Speed 2", False),
                ("t3", "Threshold 3", True),
                ("s3", "Speed 3", False),
            ):
                spin = Adw.SpinRow.new_with_range(0, 100, 1)
                spin.set_title(t(label))
                spin.set_value(float(self._curve.get(key, 0)))
                spin.connect("notify::value", self._on_curve_changed)
                curve_group.add(spin)
                self._curve_rows[key] = spin
            self._hyst_row = Adw.SpinRow.new_with_range(0, 20, 1)
            self._hyst_row.set_title(t("Hysteresis"))
            self._hyst_row.set_subtitle(t("Ignore small temperature changes"))
            self._hyst_row.set_value(float(self._curve.get("hysteresis", 3)))
            self._hyst_row.connect("notify::value", self._on_curve_changed)
            curve_group.add(self._hyst_row)

            profile_group = Adw.PreferencesGroup(title=t("Profiles"))
            profile_row = Adw.ActionRow(title=t("Fan profile"))
            save_btn = Gtk.Button(label=t("Save"))
            save_btn.set_valign(Gtk.Align.CENTER)
            save_btn.connect("clicked", lambda _b: self._save_profile())
            apply_btn = Gtk.Button(label=t("Apply"))
            apply_btn.set_valign(Gtk.Align.CENTER)
            apply_btn.add_css_class("suggested-action")
            apply_btn.connect("clicked", lambda _b: self._apply_profile())
            profile_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            profile_box.set_valign(Gtk.Align.CENTER)
            profile_box.append(save_btn)
            profile_box.append(apply_btn)
            profile_row.add_suffix(profile_box)
            profile_group.add(profile_row)
            box.append(profile_group)
        else:
            gpu_group.add(Adw.ActionRow(
                title=t("nvidia-ml-py not installed"),
                subtitle="yay -S python-nvidia-ml-py"
            ))

        # ── System fan control ───────────────────────────────────────────
        self._pwm_channels = _find_pwm_channels()
        if self._pwm_channels:
            sys_group = Adw.PreferencesGroup(title=t("System Fan Control"))
            box.append(sys_group)

            self._pwm_sliders: list[tuple] = []
            for ch in self._pwm_channels:
                row = Adw.ActionRow(title=ch["label"])
                sl = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
                sl.set_value(ch["current_pct"])
                sl.set_hexpand(True)
                sl.set_draw_value(True)
                row.add_suffix(sl)
                sys_group.add(row)
                self._pwm_sliders.append((sl, ch))

            apply_row = Adw.ActionRow()
            apply_btn = Gtk.Button(label=t("Apply"))
            apply_btn.add_css_class("suggested-action")
            apply_btn.add_css_class("pill")
            apply_btn.set_valign(Gtk.Align.CENTER)
            apply_btn.connect("clicked", self._on_apply_sys)
            apply_row.add_suffix(apply_btn)
            sys_group.add(apply_row)

        threading.Thread(target=self._poll, daemon=True).start()

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll(self):
        while self._polling:
            cpu   = read_cpu_temp()
            gpu   = read_gpu_stats()
            fans  = _read_sys_fans()
            GLib.idle_add(self._refresh, cpu, gpu, fans)
            time.sleep(2)

    def _refresh(self, cpu, gpu, fans):
        self._cpu_val.set_label(f"{cpu} °C" if cpu is not None else "--")

        if gpu:
            parts = [f"{gpu['temp']} °C"]
            if gpu["fan_pct"] is not None:
                parts.append(f"{t('Fan')}: {gpu['fan_pct']} %")
            self._gpu_stat_val.set_label("  |  ".join(parts))

            if self._auto_mode:
                temp = gpu["temp"]
                t1, t2 = int(self._curve.get("t1", 50)), int(self._curve.get("t2", 72))
                if temp < t1:
                    speed = int(self._curve.get("s1", 30))
                elif temp < t2:
                    speed = int(self._curve.get("s2", 60))
                else:
                    speed = int(self._curve.get("s3", 90))
                hysteresis = int(self._curve.get("hysteresis", 3))
                if (
                    self._last_gpu_temp is None
                    or abs(temp - self._last_gpu_temp) >= hysteresis
                    or self._last_gpu_speed is None
                ):
                    self._last_gpu_temp = temp
                    if speed != self._last_gpu_speed:
                        self._last_gpu_speed = speed
                        self._gpu_slider.set_value(speed)
                        threading.Thread(target=_set_gpu_fan, args=(speed,), daemon=True).start()
        else:
            self._gpu_stat_val.set_label("--")

        for fan in fans:
            label = fan["label"]
            rpm = fan["rpm"]
            if rpm == 0:
                if label in self._fan_rows:
                    self._fan_rows[label].set_visible(False)
                continue
            if label not in self._fan_rows:
                row = Adw.ActionRow(title=label)
                self._fan_rows[label] = row
                self._stats_group.add(row)
            self._fan_rows[label].set_visible(True)
            self._fan_rows[label].set_subtitle(f"{rpm} RPM")

    # ── GPU fan ───────────────────────────────────────────────────────────────

    def _on_auto_toggled(self, sw, _):
        self._auto_mode = sw.get_active()
        self._gpu_slider.set_sensitive(not self._auto_mode)
        self._last_gpu_speed = None
        self._last_gpu_temp = None

    def _on_curve_changed(self, *_args) -> None:
        for key, row in getattr(self, "_curve_rows", {}).items():
            self._curve[key] = int(row.get_value())
        self._curve["hysteresis"] = int(self._hyst_row.get_value())
        self._settings["curve"] = self._curve
        atomic_write_json(_FANS_SETTINGS, self._settings)
        self._last_gpu_speed = None
        self._last_gpu_temp = None

    def _save_profile(self) -> None:
        profile = {
            "auto": self._auto_mode,
            "gpu_speed": int(self._gpu_slider.get_value()) if _HAS_NVML else None,
            "sys": {ch["label"]: int(sl.get_value()) for sl, ch in getattr(self, "_pwm_sliders", [])},
        }
        self._settings["profile"] = profile
        atomic_write_json(_FANS_SETTINGS, self._settings)
        self.main_window.add_toast(Adw.Toast.new(t("Fan profile saved.")))

    def _apply_profile(self) -> None:
        profile = self._settings.get("profile")
        if not profile:
            self.main_window.add_toast(Adw.Toast.new(t("No saved fan profile.")))
            return
        if _HAS_NVML and "auto" in profile and hasattr(self, "_auto_row"):
            self._auto_row.set_active(bool(profile.get("auto")))
            self._gpu_slider.set_value(float(profile.get("gpu_speed", 50)))
        for sl, ch in getattr(self, "_pwm_sliders", []):
            value = profile.get("sys", {}).get(ch["label"])
            if value is not None:
                sl.set_value(float(value))
        if getattr(self, "_pwm_sliders", []):
            self._on_apply_sys(None)
        self.main_window.add_toast(Adw.Toast.new(t("Fan profile applied.")))

    def _on_gpu_slider(self, slider):
        if self._auto_mode:
            return
        speed = int(slider.get_value())
        if speed != self._last_gpu_speed:
            self._last_gpu_speed = speed
            threading.Thread(target=self._do_set_gpu, args=(speed,), daemon=True).start()

    def _apply_gpu_speed(self, speed: int):
        self._last_gpu_speed = speed
        if _HAS_NVML:
            self._gpu_slider.set_value(speed)
        threading.Thread(target=self._do_set_gpu, args=(speed,), daemon=True).start()

    def _do_set_gpu(self, speed: int):
        err = _set_gpu_fan(speed)
        if err:
            GLib.idle_add(self.main_window.add_toast, Adw.Toast.new(err))

    # ── System fans ───────────────────────────────────────────────────────────

    def _on_apply_sys(self, _):
        # Try without root first
        errors = []
        for sl, ch in self._pwm_sliders:
            # sl.get_value() can be fractional (continuous mouse drag), so this
            # stays as int(value / 100 * 255) rather than going through
            # caelestia_core.percent_to_pwm_raw() (which takes an
            # already-integer percent and would truncate at a different
            # point, drifting the result by up to 1/255).
            pwm_val = int(sl.get_value() / 100 * 255)
            try:
                if ch["enable"].exists():
                    ch["enable"].write_text("1\n")
                ch["pwm"].write_text(f"{pwm_val}\n")
            except PermissionError:
                errors.append(ch["pwm"])
            except Exception as e:
                self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))
                return

        if not errors:
            self.main_window.add_toast(Adw.Toast.new(t("Fan settings applied.")))
        else:
            self._show_sudo_dialog()

    def _show_sudo_dialog(self):
        dialog = Adw.MessageDialog(
            heading=t("Password required"),
            body=t("Enter your sudo password to write fan settings."),
        )
        dialog.set_transient_for(self.main_window)

        pwd_entry = Gtk.PasswordEntry()
        pwd_entry.set_show_peek_icon(True)
        pwd_entry.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8); box.set_margin_bottom(4)
        box.set_margin_start(12); box.set_margin_end(12)
        box.append(pwd_entry)
        dialog.set_extra_child(box)

        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("ok", t("Apply"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        def _on_entry_activate(_entry):
            dialog.response("ok")
            dialog.close()
        pwd_entry.connect("activate", _on_entry_activate)

        def on_resp(dlg, r):
            if r != "ok":
                return
            password = pwd_entry.get_text()
            pwd_entry.set_text("")
            if not password:
                return
            values = [
                (ch["enable"], ch["pwm"], int(sl.get_value()))
                for sl, ch in self._pwm_sliders
            ]
            threading.Thread(
                target=self._write_with_sudo, args=(values, password), daemon=True
            ).start()

        dialog.connect("response", on_resp)
        dialog.present()
        pwd_entry.grab_focus()

    def _write_with_sudo(self, values: list, password: str):
        tee_lines = []
        for enable, pwm, pct in values:
            pwm_val = caelestia_core.percent_to_pwm_raw(pct)
            if enable.exists():
                tee_lines.append(
                    f"printf '1\\n' | sudo -A tee {shlex.quote(str(enable))} > /dev/null"
                )
            tee_lines.append(
                f"printf '%d\\n' {pwm_val} | sudo -A tee {shlex.quote(str(pwm))} > /dev/null"
            )

        script = (
            "#!/usr/bin/env bash\n"
            "set -e\n\n"
            "read -r SUDO_PASSWD\n\n"
            "_ASKPASS=$(mktemp --suffix=.sh)\n"
            "chmod 700 \"$_ASKPASS\"\n"
            "cat > \"$_ASKPASS\" << 'ASKPASS_EOF'\n"
            "#!/bin/sh\n"
            "printf '%s\\n' \"$_SUDO_PASS\"\n"
            "ASKPASS_EOF\n\n"
            "export _SUDO_PASS=\"$SUDO_PASSWD\"\n"
            "export SUDO_ASKPASS=\"$_ASKPASS\"\n"
            "unset SUDO_PASSWD\n\n"
            "trap 'rm -f \"$_ASKPASS\"; unset _SUDO_PASS SUDO_ASKPASS' EXIT\n\n"
            "sudo -A -v\n\n"
        ) + "\n".join(tee_lines) + "\n"

        fd, path = tempfile.mkstemp(suffix=".sh")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(script)
            os.chmod(path, 0o700)
            proc = subprocess.run(
                [path], input=password + "\n",
                capture_output=True, text=True,
            )
            password = ""
            if proc.returncode == 0:
                GLib.idle_add(self.main_window.add_toast,
                              Adw.Toast.new(t("Fan settings applied.")))
            else:
                GLib.idle_add(self.main_window.add_toast,
                              Adw.Toast.new(t("Error (exit {code})").format(code=proc.returncode)))
        except Exception as e:
            GLib.idle_add(self.main_window.add_toast, Adw.Toast.new(t("Error: {error}").format(error=e)))
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
