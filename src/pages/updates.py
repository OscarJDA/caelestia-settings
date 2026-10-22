import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from gi.repository import Gtk, Adw, GLib
from src.lang import t
from src.safe_io import atomic_write_json, read_json

UPDATE_HISTORY = Path.home() / ".config" / "caelestia-settings" / "update_history.json"

# Schritte die das Update-Skript durchläuft — wird als Fortschritt angezeigt
UPDATE_STEPS = [
    ("yay -Syu",         t("Updating system packages…")),
    ("hyprlock",         t("Updating hyprlock…")),
    ("swww",             t("Updating swww…")),
    ("pipewire",         t("Restarting audio services…")),
    ("reboot",           t("Preparing reboot…")),
]

UPDATE_SCRIPT = """#!/usr/bin/env bash
set -e

read -r SUDO_PASSWD

# SUDO_ASKPASS helper so yay's internal sudo calls work without a TTY.
_ASKPASS=$(mktemp --suffix=.sh)
chmod 700 "$_ASKPASS"
cat > "$_ASKPASS" << 'ASKPASS_EOF'
#!/bin/sh
printf '%s\\n' "$_SUDO_PASS"
ASKPASS_EOF

export _SUDO_PASS="$SUDO_PASSWD"
export SUDO_ASKPASS="$_ASKPASS"
unset SUDO_PASSWD

trap 'rm -f "$_ASKPASS"; unset _SUDO_PASS SUDO_ASKPASS' EXIT

sudo -A -v

echo "::step:: Aktualizando paquetes del sistema…"
yay -Syu --needed hyprlock swww --noconfirm
echo "::step:: Reiniciando servicios de audio…"
systemctl --user restart pipewire.service pipewire-pulse.service wireplumber.service

echo "::done::"
if [[ "$1" == "-r" ]]; then
    echo "::step:: Preparando reinicio…"
    sleep 5
    sudo -A reboot
fi
"""


class UpdatePage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self._process = None
        self._running = False

        # ── Einstellungs-Bereich (oben) ──────────────────────────────────
        settings_group = Adw.PreferencesGroup(title=t("System Update"))
        settings_group.set_margin_top(12)
        settings_group.set_margin_start(12)
        settings_group.set_margin_end(12)
        self.append(settings_group)

        self.reboot_row = Adw.SwitchRow(
            title=t("Automatic Reboot"),
            subtitle=t("Restarts system automatically after update")
        )
        settings_group.add(self.reboot_row)

        self.available_group = Adw.PreferencesGroup(title=t("Available updates"))
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(t("Check for updates"))
        refresh_btn.connect("clicked", lambda _b: self._refresh_available())
        self.available_group.set_header_suffix(refresh_btn)
        self.available_row = Adw.ActionRow(title=t("Checking for updates…"))
        self.available_group.add(self.available_row)
        self.append(self.available_group)
        self._refresh_available()

        # Start-Button
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        btn_box.set_margin_top(12)
        btn_box.set_margin_start(12)
        btn_box.set_margin_end(12)
        btn_box.set_halign(Gtk.Align.END)

        self.start_btn = Gtk.Button(label=t("Update Now"))
        self.start_btn.add_css_class("suggested-action")
        self.start_btn.add_css_class("pill")
        self.start_btn.connect("clicked", self._on_start_clicked)
        btn_box.append(self.start_btn)
        self.append(btn_box)

        # ── Fortschritts-Bereich (mitte) ─────────────────────────────────
        self.progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.progress_box.set_margin_top(16)
        self.progress_box.set_margin_start(12)
        self.progress_box.set_margin_end(12)
        self.progress_box.set_visible(False)
        self.append(self.progress_box)

        # Aktueller Schritt-Label
        self.step_label = Gtk.Label(label="")
        self.step_label.add_css_class("heading")
        self.step_label.set_halign(Gtk.Align.START)
        self.progress_box.append(self.step_label)

        # Fortschrittsbalken
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_pulse_step(0.1)
        self.progress_box.append(self.progress_bar)

        # ── Log-Ausgabe (unten, scrollbar) ───────────────────────────────
        log_frame = Gtk.Frame()
        log_frame.set_margin_top(12)
        log_frame.set_margin_start(12)
        log_frame.set_margin_end(12)
        log_frame.set_margin_bottom(12)
        log_frame.set_vexpand(True)
        log_frame.set_visible(False)
        self.log_frame = log_frame
        self.append(log_frame)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        log_scroll.set_vexpand(True)
        log_frame.set_child(log_scroll)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_monospace(True)
        self.log_view.set_margin_top(8)
        self.log_view.set_margin_bottom(8)
        self.log_view.set_margin_start(8)
        self.log_view.set_margin_end(8)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_buffer = self.log_view.get_buffer()
        log_scroll.set_child(self.log_view)
        self._log_scroll = log_scroll

        # ── Status-Banner (Erfolg / Fehler) ──────────────────────────────
        self.result_banner = Adw.Banner()
        self.result_banner.set_revealed(False)
        self.append(self.result_banner)

        self.history_group = Adw.PreferencesGroup(title=t("Update history"))
        self.history_group.set_margin_start(12)
        self.history_group.set_margin_end(12)
        self.append(self.history_group)
        self._load_history()

    # ── Available updates & history ───────────────────────────────────────

    def _refresh_available(self) -> None:
        self.available_row.set_title(t("Checking for updates…"))
        self.available_row.set_subtitle("")

        def worker() -> None:
            if shutil.which("checkupdates"):
                out = ""
                try:
                    result = subprocess.run(
                        ["checkupdates"], capture_output=True, text=True, timeout=60
                    )
                    out = result.stdout
                except (OSError, subprocess.TimeoutExpired):
                    out = ""
            else:
                try:
                    result = subprocess.run(
                        ["pacman", "-Qu"], capture_output=True, text=True, timeout=30
                    )
                    out = result.stdout
                except (OSError, subprocess.TimeoutExpired):
                    out = ""
            packages = [line for line in out.splitlines() if line.strip()]
            GLib.idle_add(self._apply_available, packages)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_available(self, packages: list[str]) -> bool:
        if not packages:
            self.available_row.set_title(t("No updates available"))
            self.available_row.set_subtitle("")
            return False
        names = ", ".join(line.split()[0] for line in packages[:5])
        if len(packages) > 5:
            names += f" … (+{len(packages) - 5})"
        self.available_row.set_title(f"{len(packages)} {t('update(s) available')}")
        self.available_row.set_subtitle(names)
        return False

    def _load_history(self) -> None:
        for row in getattr(self, "_history_rows", []):
            try:
                self.history_group.remove(row)
            except Exception:
                pass
        self._history_rows = []
        history = read_json(UPDATE_HISTORY, {}).get("entries", [])
        if not history:
            row = Adw.ActionRow(title=t("No updates recorded yet"))
            self.history_group.add(row)
            self._history_rows.append(row)
            return
        for entry in history[-5:][::-1]:
            row = Adw.ActionRow(
                title=entry.get("time", "?"),
                subtitle=("✓ " if entry.get("success") else "✗ ") + entry.get("message", ""),
            )
            self.history_group.add(row)
            self._history_rows.append(row)

    def _record_history(self, success: bool, message: str) -> None:
        data = read_json(UPDATE_HISTORY, {})
        entries = data.get("entries", [])
        entries.append(
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "success": success,
                "message": message,
            }
        )
        data["entries"] = entries[-50:]
        atomic_write_json(UPDATE_HISTORY, data)
        self._load_history()

    # ── Update starten ────────────────────────────────────────────────────

    def _on_start_clicked(self, _btn):
        if self._running:
            return
        self._show_password_dialog()

    def _show_password_dialog(self):
        dialog = Adw.MessageDialog(
            heading=t("Password required"),
            body=t("Enter your sudo password to start the system update."),
        )
        dialog.set_transient_for(self.main_window)

        # Passwort-Eingabe
        pwd_entry = Gtk.PasswordEntry()
        pwd_entry.set_hexpand(True)
        pwd_entry.set_show_peek_icon(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(4)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Benutzer-Info
        user_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        user_icon = Gtk.Image.new_from_icon_name("system-users-symbolic")
        user_label = Gtk.Label(label=os.environ.get("USER", "user"))
        user_label.add_css_class("heading")
        user_row.append(user_icon)
        user_row.append(user_label)
        user_row.set_halign(Gtk.Align.CENTER)
        box.append(user_row)
        box.append(pwd_entry)

        dialog.set_extra_child(box)
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("ok",     t("Start update"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")

        # Enter in Passwortfeld → Dialog bestätigen und schließen
        def on_entry_activate(_entry):
            dialog.response("ok")
            dialog.close()
        pwd_entry.connect("activate", on_entry_activate)

        def on_response(dlg, response):
            if response == "ok":
                password = pwd_entry.get_text()
                pwd_entry.set_text("")   # Passwort sofort aus Widget löschen
                if password:
                    self._start_update(password)
                else:
                    self.main_window.add_toast(Adw.Toast.new(t("No password entered.")))

        dialog.connect("response", on_response)
        dialog.present()
        # Fokus direkt ins Passwortfeld
        pwd_entry.grab_focus()

    def _start_update(self, password: str):
        self._running = True
        self.start_btn.set_sensitive(False)
        self.start_btn.set_label(t("Running..."))
        self.result_banner.set_revealed(False)

        # UI einblenden
        self.progress_box.set_visible(True)
        self.log_frame.set_visible(True)

        # Log leeren
        self.log_buffer.set_text("")
        self.step_label.set_text(t("Starting update..."))
        self.progress_bar.set_fraction(0.0)

        # Skript in user-only tempfile schreiben
        fd, script_path = tempfile.mkstemp(suffix=".sh")
        helper = "paru" if shutil.which("paru") and not shutil.which("yay") else "yay"
        script = UPDATE_SCRIPT.replace("yay ", f"{helper} ", 1)
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(script_path, 0o700)

        args = [script_path]
        if self.reboot_row.get_active():
            args.append("-r")

        threading.Thread(target=self._run_update, args=(args, password, script_path), daemon=True).start()

    def _run_update(self, args: list[str], password: str, script_path: str | None = None):
        try:
            self._process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            # Passwort auf stdin schreiben — Skript liest es mit `read`
            self._process.stdin.write(password + "\n")
            self._process.stdin.flush()
            self._process.stdin.close()
            password = ""   # Passwort sofort aus Speicher löschen

            step_count = 0
            total_steps = UPDATE_SCRIPT.count("::step::")

            for line in self._process.stdout:
                line = line.rstrip()
                if line.startswith("::step::"):
                    step_count += 1
                    msg = line.replace("::step::", "").strip()
                    fraction = min(step_count / max(total_steps, 1), 0.95)
                    GLib.idle_add(self._update_step, msg, fraction)
                elif line == "::done::":
                    GLib.idle_add(self._update_step, t("Done!"), 1.0)
                else:
                    GLib.idle_add(self._append_log, line)

            self._process.wait()
            rc = self._process.returncode

            if rc == 0:
                GLib.idle_add(self._on_finished, True, t("Update successful."))
                subprocess.run([
                    "notify-send", "Caelestia Settings",
                    "System update completed successfully.",
                    "--icon=software-update-available", "--urgency=normal",
                ], capture_output=True)
            else:
                GLib.idle_add(self._on_finished, False, t("Update failed (exit code {code}).").format(code=rc))
                subprocess.run([
                    "notify-send", "Caelestia Settings",
                    t("Update failed (exit code {code}).").format(code=rc),
                    "--icon=dialog-error", "--urgency=critical",
                ], capture_output=True)

        except Exception as e:
            GLib.idle_add(self._on_finished, False, t("Error: {error}").format(error=e))
        finally:
            if script_path:
                try:
                    os.unlink(script_path)
                except Exception:
                    pass

    # ── UI-Updates aus Thread (immer via idle_add) ────────────────────────

    def _update_step(self, msg: str, fraction: float):
        self.step_label.set_text(msg)
        self.progress_bar.set_fraction(fraction)
        self._append_log(f"▶ {msg}")

    def _append_log(self, line: str):
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, line + "\n")
        # Auto-scroll ans Ende
        adj = self._log_scroll.get_vadjustment()
        adj.set_value(adj.get_upper())

    def _on_finished(self, success: bool, message: str):
        self._running = False
        self.start_btn.set_sensitive(True)
        self.start_btn.set_label(t("Update Now"))

        if success:
            self.result_banner.add_css_class("success")
            self.result_banner.remove_css_class("error")
        else:
            self.result_banner.add_css_class("error")
            self.result_banner.remove_css_class("success")

        self.result_banner.set_title(message)
        self.result_banner.set_revealed(True)
        self.main_window.add_toast(Adw.Toast.new(message))
        try:
            self._record_history(success, message)
        except Exception as exc:
            print(f"Update history failed: {exc}")