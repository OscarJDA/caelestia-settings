"""Audio output, input, balance and per-application streams (D2)."""

from __future__ import annotations

import json
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.lang import t  # noqa: E402


def _run(args: list[str], timeout: int = 3) -> tuple[int, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"audio command failed: {exc}")
        return 1, ""


def _json(args: list[str]) -> list[dict]:
    rc, out = _run(args)
    if rc != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _volume_percent(volume: dict) -> int:
    for channel in ("front-left", "mono", "left"):
        value = volume.get(channel) if isinstance(volume, dict) else None
        if isinstance(value, dict) and value.get("value_percent"):
            try:
                return int(str(value["value_percent"]).rstrip("%"))
            except ValueError:
                pass
    return 0


class AudioPage(Adw.PreferencesPage):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self._loading = False
        self._sinks: list[dict] = []
        self._sources: list[dict] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        output = Adw.PreferencesGroup(title=t("Output"))
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_valign(Gtk.Align.CENTER)
        self.output_combo.connect("changed", self._on_output_changed)
        row = Adw.ActionRow(title=t("Output device"))
        row.add_suffix(self.output_combo)
        output.add(row)

        self.output_mute = Adw.SwitchRow(title=t("Mute output"))
        self.output_mute.connect("notify::active", self._on_output_mute)
        output.add(self.output_mute)

        row = Adw.ActionRow(title=t("Volume"))
        self.output_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.output_volume.set_hexpand(True)
        self.output_volume.set_draw_value(True)
        self.output_volume.set_size_request(220, -1)
        self.output_volume.connect("value-changed", self._on_output_volume)
        row.add_suffix(self.output_volume)
        output.add(row)

        row = Adw.ActionRow(title=t("Balance"), subtitle=t("Left / right"))
        self.balance = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -100, 100, 2)
        self.balance.set_hexpand(True)
        self.balance.set_draw_value(True)
        self.balance.set_size_request(220, -1)
        self.balance.connect("value-changed", self._on_balance)
        row.add_suffix(self.balance)
        output.add(row)
        self.add(output)

        input_group = Adw.PreferencesGroup(title=t("Input"))
        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.set_valign(Gtk.Align.CENTER)
        self.input_combo.connect("changed", self._on_input_changed)
        row = Adw.ActionRow(title=t("Input device"))
        row.add_suffix(self.input_combo)
        input_group.add(row)

        self.input_mute = Adw.SwitchRow(title=t("Mute input"))
        self.input_mute.connect("notify::active", self._on_input_mute)
        input_group.add(self.input_mute)

        row = Adw.ActionRow(title=t("Input volume"))
        self.input_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.input_volume.set_hexpand(True)
        self.input_volume.set_draw_value(True)
        self.input_volume.set_size_request(220, -1)
        self.input_volume.connect("value-changed", self._on_input_volume)
        row.add_suffix(self.input_volume)
        input_group.add(row)
        self.add(input_group)

        self.streams_group = Adw.PreferencesGroup(
            title=t("Applications"),
            description=t("Per-application streams. Start playback to see them here."),
        )
        header = Gtk.Button(icon_name="view-refresh-symbolic")
        header.set_tooltip_text(t("Refresh application streams"))
        header.connect("clicked", lambda _b: self._refresh_streams())
        self.streams_group.set_header_suffix(header)
        self.add(self.streams_group)
        self._streams_loaded = False

    def refresh(self) -> None:
        self._loading = True
        self._sinks = _json(["pactl", "-f", "json", "list", "sinks"])
        self._sources = [
            src for src in _json(["pactl", "-f", "json", "list", "sources"])
            if not str(src.get("name", "")).endswith(".monitor")
        ]
        default_sink = _run(["pactl", "get-default-sink"])[1].strip()
        default_source = _run(["pactl", "get-default-source"])[1].strip()

        self.output_combo.remove_all()
        active = 0
        for index, sink in enumerate(self._sinks):
            self.output_combo.append(sink.get("name", ""), sink.get("description", sink.get("name", "")))
            if sink.get("name") == default_sink:
                active = index
        if self._sinks:
            self.output_combo.set_active(active)

        self.input_combo.remove_all()
        active = 0
        for index, source in enumerate(self._sources):
            self.input_combo.append(source.get("name", ""), source.get("description", source.get("name", "")))
            if source.get("name") == default_source:
                active = index
        if self._sources:
            self.input_combo.set_active(active)

        self._load_sink_state()
        self._load_source_state()
        self._loading = False
        self._refresh_streams()

    def _current_sink(self) -> dict | None:
        name = self.output_combo.get_active_id()
        return next((sink for sink in self._sinks if sink.get("name") == name), None)

    def _current_source(self) -> dict | None:
        name = self.input_combo.get_active_id()
        return next((source for source in self._sources if source.get("name") == name), None)

    def _load_sink_state(self) -> None:
        sink = self._current_sink()
        if not sink:
            return
        self.output_mute.set_active(bool(sink.get("mute", False)))
        self.output_volume.set_value(_volume_percent(sink.get("volume", {})))
        try:
            self.balance.set_value(float(sink.get("balance", 0.0)) * 100)
        except (TypeError, ValueError):
            self.balance.set_value(0)

    def _load_source_state(self) -> None:
        source = self._current_source()
        if not source:
            return
        self.input_mute.set_active(bool(source.get("mute", False)))
        self.input_volume.set_value(_volume_percent(source.get("volume", {})))

    def _on_output_changed(self, _combo) -> None:
        if self._loading:
            return
        sink = self.output_combo.get_active_id()
        if sink:
            _run(["pactl", "set-default-sink", sink])
            self._loading = True
            self._load_sink_state()
            self._loading = False

    def _on_input_changed(self, _combo) -> None:
        if self._loading:
            return
        source = self.input_combo.get_active_id()
        if source:
            _run(["pactl", "set-default-source", source])
            self._loading = True
            self._load_source_state()
            self._loading = False

    def _on_output_mute(self, row, _pspec) -> None:
        if self._loading:
            return
        _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if row.get_active() else "0"])

    def _on_input_mute(self, row, _pspec) -> None:
        if self._loading:
            return
        _run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if row.get_active() else "0"])

    def _on_output_volume(self, scale) -> None:
        if self._loading:
            return
        _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(scale.get_value())}%"])

    def _on_input_volume(self, scale) -> None:
        if self._loading:
            return
        _run(["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{int(scale.get_value())}%"])

    def _on_balance(self, scale) -> None:
        if self._loading:
            return
        value = scale.get_value() / 100.0
        volume = max(0, int(self.output_volume.get_value()))
        left = max(0, min(150, int(volume * (1.0 - value))))
        right = max(0, min(150, int(volume * (1.0 + value))))
        _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{left}%", f"{right}%"])

    def _refresh_streams(self) -> None:
        for row in getattr(self, "_stream_rows_all", []):
            try:
                self.streams_group.remove(row)
            except Exception:
                pass
        self._stream_rows_all = []

        streams = _json(["pactl", "-f", "json", "list", "sink-inputs"])
        if not streams:
            row = Adw.ActionRow(title=t("No application streams"), subtitle=t("Start playback in an app to see it here."))
            self.streams_group.add(row)
            self._stream_rows_all.append(row)
            return

        for stream in streams:
            index = stream.get("index")
            props = stream.get("properties", {}) or {}
            name = props.get("application.name") or props.get("media.name") or f"Stream {index}"
            row = Adw.ActionRow(title=str(name), subtitle=props.get("media.name", ""))
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_valign(Gtk.Align.CENTER)

            mute = Gtk.Switch()
            mute.set_valign(Gtk.Align.CENTER)
            mute.set_active(bool(stream.get("mute", False)))
            mute.connect("notify::active", lambda sw, _p, i=index: _run(
                ["pactl", "set-sink-input-mute", str(i), "1" if sw.get_active() else "0"]
            ))
            box.append(mute)

            volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
            volume.set_size_request(140, -1)
            volume.set_draw_value(True)
            volume.set_value(_volume_percent(stream.get("volume", {})))
            volume.connect("value-changed", lambda sl, _p, i=index: _run(
                ["pactl", "set-sink-input-volume", str(i), f"{int(sl.get_value())}%"]
            ))
            box.append(volume)

            row.add_suffix(box)
            self.streams_group.add(row)
            self._stream_rows_all.append(row)
