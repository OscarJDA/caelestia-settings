"""Screenshots and screen recording (D11)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.safe_io import atomic_write_json, read_json
from src.lang import t  # noqa: E402

SETTINGS_FILE = Path.home() / ".config" / "caelestia-settings" / "capture.json"


def _default_pictures() -> Path:
    return Path(os.environ.get("XDG_PICTURES_DIR", Path.home() / "Pictures"))


class CapturePage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._settings = read_json(SETTINGS_FILE, {})
        self._recorder: subprocess.Popen | None = None
        self._record_path: Path | None = None
        self._build()
        GLib.timeout_add_seconds(1, self._poll_recorder)
        self.connect("destroy", lambda _w: self._stop_recording())

    def _build(self) -> None:
        shots = Adw.PreferencesGroup(title=t("Screenshots"))
        self._shot_dir = Adw.EntryRow(title=t("Save folder"))
        self._shot_dir.set_text(self._settings.get("screenshotDir", str(_default_pictures() / "Screenshots")))
        self._shot_dir.connect("changed", lambda _r: self._save_settings())
        shots.add(self._shot_dir)

        row = Adw.ActionRow(title=t("Take a screenshot"), subtitle=t("Full screen or select an area"))
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        full = Gtk.Button(label=t("Full screen"))
        full.connect("clicked", lambda _b: self._screenshot(None))
        area = Gtk.Button(label=t("Select area"))
        area.connect("clicked", lambda _b: self._screenshot_area())
        box.append(full)
        box.append(area)
        row.add_suffix(box)
        shots.add(row)
        if not shutil.which("grim"):
            row.set_subtitle(t("grim is not installed"))
            full.set_sensitive(False)
            area.set_sensitive(False)
        self.add(shots)

        recording = Adw.PreferencesGroup(
            title=t("Screen recording"),
            description=t("Uses wf-recorder. Audio recording uses the default source."),
        )
        self._record_dir = Adw.EntryRow(title=t("Save folder"))
        self._record_dir.set_text(self._settings.get("recordDir", str(_default_pictures())))
        self._record_dir.connect("changed", lambda _r: self._save_settings())
        recording.add(self._record_dir)

        self._format = Adw.ComboRow(title=t("Format"))
        self._format.set_model(Gtk.StringList.new(["mp4", "mkv", "webm"]))
        fmt = self._settings.get("format", "mp4")
        self._format.set_selected(["mp4", "mkv", "webm"].index(fmt) if fmt in ("mp4", "mkv", "webm") else 0)
        self._format.connect("notify::selected", lambda _r, _p: self._save_settings())
        recording.add(self._format)

        self._fps = Adw.SpinRow.new_with_range(15, 120, 1)
        self._fps.set_title(t("Framerate"))
        self._fps.set_value(float(self._settings.get("fps", 60)))
        self._fps.connect("notify::value", lambda _r, _p: self._save_settings())
        recording.add(self._fps)

        self._audio = Adw.SwitchRow(title=t("Record audio"))
        self._audio.set_active(bool(self._settings.get("audio", False)))
        self._audio.connect("notify::active", lambda _r, _p: self._save_settings())
        recording.add(self._audio)

        control = Adw.ActionRow(title=t("Recording"))
        self._record_status = Gtk.Label(label=t("Idle"))
        self._record_status.add_css_class("dim-label")
        self._record_status.set_valign(Gtk.Align.CENTER)
        start = Gtk.Button(label=t("Start"))
        start.add_css_class("suggested-action")
        start.connect("clicked", lambda _b: self._start_recording())
        stop = Gtk.Button(label=t("Stop"))
        stop.connect("clicked", lambda _b: self._stop_recording())
        control.add_suffix(self._record_status)
        control.add_suffix(start)
        control.add_suffix(stop)
        recording.add(control)
        if not shutil.which("wf-recorder"):
            control.set_subtitle(t("wf-recorder is not installed"))
            start.set_sensitive(False)
            stop.set_sensitive(False)
        self.add(recording)

    def _save_settings(self) -> None:
        self._settings.update(
            {
                "screenshotDir": self._shot_dir.get_text().strip(),
                "recordDir": self._record_dir.get_text().strip(),
                "format": ["mp4", "mkv", "webm"][max(0, self._format.get_selected())],
                "fps": int(self._fps.get_value()),
                "audio": self._audio.get_active(),
            }
        )
        atomic_write_json(SETTINGS_FILE, self._settings)

    def _screen_path(self, folder: Path, extension: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"screenshot-{datetime.now():%Y%m%d-%H%M%S}.{extension}"

    def _screenshot(self, geometry: str | None) -> None:
        folder = Path(self._shot_dir.get_text().strip() or _default_pictures() / "Screenshots").expanduser()
        path = self._screen_path(folder, "png")
        args = ["grim"]
        if geometry:
            args += ["-g", geometry]
        args.append(str(path))
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=20)
            if result.returncode == 0:
                self.main_window.add_toast(Adw.Toast.new(t("Screenshot saved: {name}").format(name=path.name)))
            else:
                self.main_window.add_toast(Adw.Toast.new(t("Screenshot failed")))
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Screenshot failed: {error}").format(error=exc)))

    def _screenshot_area(self) -> None:
        if not shutil.which("slurp"):
            self.main_window.add_toast(Adw.Toast.new(t("slurp is not installed")))
            return

        def worker() -> None:
            try:
                result = subprocess.run(["slurp"], capture_output=True, text=True, timeout=60)
                geometry = result.stdout.strip()
                if result.returncode == 0 and geometry:
                    GLib.idle_add(self._screenshot, geometry)
            except (OSError, subprocess.TimeoutExpired):
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _start_recording(self) -> None:
        if self._recorder is not None:
            return
        folder = Path(self._record_dir.get_text().strip() or _default_pictures()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        extension = ["mp4", "mkv", "webm"][max(0, self._format.get_selected())]
        path = folder / f"recording-{datetime.now():%Y%m%d-%H%M%S}.{extension}"
        args = ["wf-recorder", "-f", str(path), "-r", str(int(self._fps.get_value()))]
        if self._audio.get_active():
            args.append("--audio")
        try:
            self._recorder = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._record_path = path
            self._record_status.set_label(t("Recording…"))
            self.main_window.add_toast(Adw.Toast.new(t("Recording to {name}").format(name=path.name)))
        except OSError as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Recording failed: {error}").format(error=exc)))
            self._recorder = None

    def _stop_recording(self) -> None:
        if self._recorder is None:
            return
        try:
            self._recorder.send_signal(signal.SIGINT)
            self._recorder.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                self._recorder.kill()
            except OSError:
                pass
        self._recorder = None
        self._record_status.set_label(t("Idle"))
        if self._record_path is not None:
            self.main_window.add_toast(Adw.Toast.new(t("Recording saved: {name}").format(name=self._record_path.name)))
            self._record_path = None

    def _poll_recorder(self) -> bool:
        if self._recorder is not None and self._recorder.poll() is not None:
            self._recorder = None
            self._record_status.set_label(t("Idle"))
        return True
