"""Desktop widget configuration for the Caelestia shell.

The clock and audio visualiser are native Caelestia background widgets and are
stored in ``shell.json``.  System, weather, media and calendar widgets are
rendered by the shell fork and stored in ``desktop_widgets.json`` so the shell
can read them without a plugin rebuild.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.config import CAELESTIA_SHELL_JSON
from src.lang import t
from src.settings_engine import JsonFileBackend, ShellBackend, make_backend_error_toast

DESKTOP_WIDGETS_FILE = Path.home() / ".config" / "caelestia-settings" / "desktop_widgets.json"

WIDGET_CORNER_CHOICES = (
    ("top-left", "Top left"),
    ("top-center", "Top center"),
    ("top-right", "Top right"),
    ("middle-left", "Middle left"),
    ("middle-center", "Middle center"),
    ("middle-right", "Middle right"),
    ("bottom-left", "Bottom left"),
    ("bottom-center", "Bottom center"),
    ("bottom-right", "Bottom right"),
)

DEFAULT_DESKTOP_WIDGETS = {
    "version": 1,
    "widgets": {
        "system": {
            "enabled": True,
            "corner": "top-center",
            "scale": 1.0,
            "showCpu": True,
            "showGpu": True,
            "showMemory": True,
            "showStorage": True,
            "showNetwork": True,
        },
        "weather": {"enabled": True, "corner": "top-right", "scale": 1.0},
        "media": {"enabled": True, "corner": "bottom-left", "scale": 1.0},
        "calendar": {"enabled": True, "corner": "bottom-center", "scale": 1.0},
    },
}


class DesktopWidgetsPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._loading = False
        self._bindings: list[tuple] = []
        self.shell = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        self.widgets = JsonFileBackend(
            DESKTOP_WIDGETS_FILE,
            DEFAULT_DESKTOP_WIDGETS,
            error_sink=make_backend_error_toast(main_window),
        )
        self._build()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _switch(self, group, backend, key, title, default=False, subtitle=""):
        row = Adw.SwitchRow(
            title=t(title),
            subtitle=t(subtitle) if subtitle else None,
        )
        row.set_active(bool(backend.get(key, default=default)))
        self._bindings.append((row, backend, key, default, "switch"))

        def on_toggle(widget, _pspec):
            if not self._loading:
                backend.set(key, widget.get_active())

        row.connect("notify::active", on_toggle)
        group.add(row)
        return row

    def _combo(self, group, backend, key, title, choices, default):
        row = Adw.ActionRow(title=t(title))
        combo = Gtk.ComboBoxText()
        combo.set_valign(Gtk.Align.CENTER)
        for value, label in choices:
            combo.append(value, t(label))
        combo.set_active_id(str(backend.get(key, default=default)))
        if combo.get_active_id() is None:
            combo.set_active(0)
        self._bindings.append((combo, backend, key, default, "combo"))

        def on_changed(widget):
            if not self._loading:
                value = widget.get_active_id()
                if value is not None:
                    backend.set(key, value)

        combo.connect("changed", on_changed)
        row.add_suffix(combo)
        group.add(row)
        return combo

    def _number(self, group, backend, key, title, default, minimum, maximum, step, digits=0, kind="float"):
        row = Adw.SpinRow.new_with_range(minimum, maximum, step)
        row.set_title(t(title))
        row.set_digits(digits)
        row.set_value(float(backend.get(key, default=default)))
        self._bindings.append((row, backend, key, default, "number", kind, digits))

        def on_change(widget, _pspec):
            if self._loading:
                return
            value = widget.get_value()
            backend.set(key, int(round(value)) if kind == "int" else round(value, digits))

        row.connect("notify::value", on_change)
        group.add(row)
        return row

    def _build(self) -> None:
        clock = Adw.PreferencesGroup(
            title=t("Desktop clock"),
            description=t("Native clock widget rendered by Caelestia on the desktop."),
        )
        self._switch(clock, self.shell, "background.desktopClock.enabled", "Show clock", False)
        self._combo(
            clock,
            self.shell,
            "background.desktopClock.position",
            "Position",
            WIDGET_CORNER_CHOICES,
            "bottom-right",
        )
        self._number(
            clock,
            self.shell,
            "background.desktopClock.scale",
            "Scale",
            1.0,
            0.5,
            3.0,
            0.05,
            2,
        )
        self._switch(
            clock,
            self.shell,
            "background.desktopClock.invertColors",
            "Invert colours",
            False,
        )
        self._switch(
            clock,
            self.shell,
            "background.desktopClock.background.enabled",
            "Background",
            False,
        )
        self._number(
            clock,
            self.shell,
            "background.desktopClock.background.opacity",
            "Background opacity",
            0.7,
            0.0,
            1.0,
            0.05,
            2,
        )
        self._switch(
            clock,
            self.shell,
            "background.desktopClock.background.blur",
            "Blur background",
            True,
        )
        self._switch(
            clock,
            self.shell,
            "background.desktopClock.shadow.enabled",
            "Shadow",
            True,
        )
        self._number(
            clock,
            self.shell,
            "background.desktopClock.shadow.opacity",
            "Shadow opacity",
            0.7,
            0.0,
            1.0,
            0.05,
            2,
        )
        self._number(
            clock,
            self.shell,
            "background.desktopClock.shadow.blur",
            "Shadow blur",
            0.4,
            0.0,
            1.0,
            0.05,
            2,
        )
        self.add(clock)

        visualiser = Adw.PreferencesGroup(
            title=t("Audio visualiser"),
            description=t("Native audio visualiser rendered behind desktop windows."),
        )
        self._switch(
            visualiser,
            self.shell,
            "background.visualiser.enabled",
            "Enable visualiser",
            False,
        )
        self._switch(
            visualiser,
            self.shell,
            "background.visualiser.autoHide",
            "Auto-hide",
            True,
            "Hide when there are no floating windows",
        )
        self._switch(
            visualiser,
            self.shell,
            "background.visualiser.blur",
            "Blur wallpaper",
            False,
        )
        self._number(
            visualiser,
            self.shell,
            "background.visualiser.rounding",
            "Rounding scale",
            1.0,
            0.0,
            2.0,
            0.05,
            2,
        )
        self._number(
            visualiser,
            self.shell,
            "background.visualiser.spacing",
            "Spacing scale",
            1.0,
            0.0,
            2.0,
            0.05,
            2,
        )
        self.add(visualiser)

        system = Adw.PreferencesGroup(
            title=t("System monitor"),
            description=t("CPU, GPU, memory, storage and network usage."),
        )
        self._switch(system, self.widgets, "widgets.system.enabled", "Show widget", True)
        self._combo(
            system,
            self.widgets,
            "widgets.system.corner",
            "Corner",
            WIDGET_CORNER_CHOICES,
            "top-center",
        )
        self._number(
            system,
            self.widgets,
            "widgets.system.scale",
            "Scale",
            1.0,
            0.6,
            2.0,
            0.05,
            2,
        )
        self._switch(system, self.widgets, "widgets.system.showCpu", "Show CPU", True)
        self._switch(system, self.widgets, "widgets.system.showGpu", "Show GPU", True)
        self._switch(system, self.widgets, "widgets.system.showMemory", "Show memory", True)
        self._switch(system, self.widgets, "widgets.system.showStorage", "Show storage", True)
        self._switch(system, self.widgets, "widgets.system.showNetwork", "Show network", True)
        self.add(system)

        weather = Adw.PreferencesGroup(title=t("Weather"))
        self._switch(weather, self.widgets, "widgets.weather.enabled", "Show widget", True)
        self._combo(
            weather,
            self.widgets,
            "widgets.weather.corner",
            "Corner",
            WIDGET_CORNER_CHOICES,
            "top-right",
        )
        self._number(
            weather,
            self.widgets,
            "widgets.weather.scale",
            "Scale",
            1.0,
            0.6,
            2.0,
            0.05,
            2,
        )
        self.add(weather)

        media = Adw.PreferencesGroup(title=t("Media"))
        self._switch(media, self.widgets, "widgets.media.enabled", "Show widget", True)
        self._combo(
            media,
            self.widgets,
            "widgets.media.corner",
            "Corner",
            WIDGET_CORNER_CHOICES,
            "bottom-left",
        )
        self._number(
            media,
            self.widgets,
            "widgets.media.scale",
            "Scale",
            1.0,
            0.6,
            2.0,
            0.05,
            2,
        )
        self.add(media)

        calendar = Adw.PreferencesGroup(title=t("Calendar"))
        self._switch(calendar, self.widgets, "widgets.calendar.enabled", "Show widget", True)
        self._combo(
            calendar,
            self.widgets,
            "widgets.calendar.corner",
            "Corner",
            WIDGET_CORNER_CHOICES,
            "bottom-center",
        )
        self._number(
            calendar,
            self.widgets,
            "widgets.calendar.scale",
            "Scale",
            1.0,
            0.6,
            2.0,
            0.05,
            2,
        )
        self.add(calendar)

    def reload_values(self) -> None:
        self._loading = True
        try:
            for binding in self._bindings:
                widget, backend, key, default, kind = binding[:5]
                value = backend.get(key, default=default)
                if kind == "switch":
                    widget.set_active(bool(value))
                elif kind == "combo":
                    if not widget.set_active_id(str(value)):
                        widget.set_active(0)
                elif kind == "number":
                    widget.set_value(float(value))
        finally:
            self._loading = False
