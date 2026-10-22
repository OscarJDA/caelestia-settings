"""Searchable browser for every Hyprland config option (A4).

The catalogue is generated from Hyprland's own ConfigValues.cpp. Rows are
built on demand (only for the current search/filter) so opening the app does
not shell out for all 350 options.
"""

from __future__ import annotations

import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.hypr_options_catalog import OPTIONS, SECTIONS
from src.hypr_settings import HyprBackend
from src.settings_engine import make_backend_error_toast
from src.lang import t  # noqa: E402

_RESULT_LIMIT = 60

_KIND = {
    "Bool": "bool",
    "Int": "int",
    "Float": "float",
    "String": "string",
    "FontWeight": "int",
}

_CHOICE_RE = re.compile(r"\[([^\]]+)\]")


def _choices(description: str) -> list[str]:
    match = _CHOICE_RE.search(description)
    if not match:
        return []
    raw = match.group(1)
    if "/" not in raw:
        return []
    values = [part.strip() for part in raw.split("/") if part.strip()]
    return values if len(values) > 1 else []


def _type_label(type_name: str) -> str:
    return {
        "Bool": t("boolean"),
        "Int": t("integer"),
        "Float": t("decimal"),
        "String": t("text"),
        "FontWeight": t("font weight"),
        "CssGap": t("gap"),
        "Gradient": t("gradient"),
        "Color": t("colour"),
        "Vec2": t("vector"),
    }.get(type_name, type_name)


class HyprOptionsPage(Adw.PreferencesPage):
    def __init__(self, main_window, backend: HyprBackend | None = None):
        super().__init__()
        self.main_window = main_window
        self.backend = backend or HyprBackend(error_sink=make_backend_error_toast(main_window))
        self._groups: list[Adw.PreferencesGroup] = []
        self._timer = 0
        self._search: Gtk.SearchEntry | None = None
        self._section: Gtk.DropDown | None = None
        self._count_row: Adw.ActionRow | None = None
        self._build_filter()
        self._show_hint(t("Type to search {count} Hyprland options.").format(count=len(OPTIONS)))

    def _build_filter(self) -> None:
        group = Adw.PreferencesGroup(
            title=t("All Hyprland options"),
            description=t("Raw access to every option exposed by the running compositor. Changes are written to the managed override layer."),
        )

        search_row = Adw.ActionRow(title=t("Search"))
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(t("gaps, blur, vrr, scroll…"))
        self._search.set_width_chars(26)
        self._search.set_valign(Gtk.Align.CENTER)
        self._search.connect("search-changed", self._on_search_changed)
        search_row.add_suffix(self._search)
        group.add(search_row)

        section_row = Adw.ActionRow(title=t("Section"))
        self._section = Gtk.DropDown.new_from_strings([t("All sections"), *SECTIONS])
        self._section.set_valign(Gtk.Align.CENTER)
        self._section.connect("notify::selected", lambda *_: self._schedule_rebuild(0))
        section_row.add_suffix(self._section)
        group.add(section_row)

        self._count_row = Adw.ActionRow(title=t("Results"), subtitle=t("Start typing to filter"))
        group.add(self._count_row)

        self.add(group)
        self._groups.append(group)

    def focus_default(self) -> None:
        if self._search:
            self._search.grab_focus()

    def _show_hint(self, text: str) -> None:
        group = Adw.PreferencesGroup()
        row = Adw.ActionRow(title=text, subtitle=t("Use the search box above to narrow it down."))
        group.add(row)
        self.add(group)
        self._groups.append(group)
        if self._count_row:
            self._count_row.set_subtitle(text)

    def _on_search_changed(self, _entry) -> None:
        self._schedule_rebuild(250)

    def _schedule_rebuild(self, delay: int) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

        def run() -> bool:
            self._timer = 0
            self._rebuild()
            return False

        self._timer = GLib.timeout_add(delay, run)

    def _clear_results(self) -> None:
        for group in self._groups[1:]:
            try:
                self.remove(group)
            except Exception:
                pass
        self._groups = self._groups[:1]

    def _rebuild(self) -> None:
        self._clear_results()
        query = self._search.get_text().strip().casefold() if self._search else ""
        section_index = self._section.get_selected() if self._section else 0
        section = "" if section_index == 0 else SECTIONS[section_index - 1]

        if not query and not section:
            self._show_hint(t("Type to search {count} Hyprland options.").format(count=len(OPTIONS)))
            return

        matches = [
            item
            for item in OPTIONS
            if (not section or item[0].startswith(section + ":"))
            and (not query or query in item[0].casefold() or query in item[1].casefold())
        ]
        total = len(matches)
        matches = matches[:_RESULT_LIMIT]
        if self._count_row:
            suffix = t(" — showing first {count}").format(count=len(matches)) if total > len(matches) else ""
            self._count_row.set_subtitle(t("{count} matching option(s){suffix}").format(count=total, suffix=suffix))

        current_section = None
        group = None
        for name, description, type_name in matches:
            if not self.backend.available(name):
                continue
            prefix = name.split(":", 1)[0]
            if prefix != current_section:
                group = Adw.PreferencesGroup(title=prefix)
                self.add(group)
                self._groups.append(group)
                current_section = prefix
            row = self._build_row(name, description, type_name)
            if row is not None:
                group.add(row)

        if len(self._groups) == 1:
            self._show_hint("No matching options.")

    def _build_row(self, name: str, description: str, type_name: str) -> Gtk.Widget | None:
        kind = _KIND.get(type_name)
        value = self.backend.get(name, kind=kind, default=None)
        choices = _choices(description)

        if not kind:
            row = Adw.ActionRow(title=name, subtitle=f"{description} · {_type_label(type_name)}")
            label = Gtk.Label(label=str(value) if value is not None else "—")
            label.add_css_class("dim-label")
            label.set_valign(Gtk.Align.CENTER)
            row.add_suffix(label)
            return row

        if kind == "bool":
            row = Adw.SwitchRow(title=name, subtitle=description)
            row.set_active(bool(value))
            row.connect("notify::active", lambda widget, _p: self._save(name, widget.get_active()))
            return self._with_reset(row, name)

        if choices and kind in ("int", "string"):
            row = Adw.ComboRow(title=name, subtitle=description)
            row.set_model(Gtk.StringList.new(choices))
            try:
                row.set_selected(choices.index(str(value)))
            except ValueError:
                row.set_selected(0)
            row.connect(
                "notify::selected",
                lambda widget, _p: self._save(
                    name,
                    int(choices[widget.get_selected()]) if kind == "int" else choices[widget.get_selected()],
                ),
            )
            return self._with_reset(row, name)

        if kind in ("int", "float"):
            row = Adw.SpinRow.new_with_range(-100000, 100000, 1 if kind == "int" else 0.1)
            row.set_title(name)
            row.set_subtitle(description)
            row.set_digits(0 if kind == "int" else 3)
            try:
                row.set_value(float(value if value is not None else 0))
            except (TypeError, ValueError):
                row.set_value(0)
            row.connect(
                "notify::value",
                lambda widget, _p: self._schedule_save(
                    name,
                    int(round(widget.get_value())) if kind == "int" else float(widget.get_value()),
                ),
            )
            return self._with_reset(row, name)

        row = Adw.EntryRow(title=name)
        row.set_tooltip_text(f"{description} · {_type_label(type_name)}")
        row.set_show_apply_button(True)
        row.set_text("" if value is None else str(value))

        def commit(_widget=None) -> None:
            self._save(name, row.get_text())

        row.connect("apply", commit)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", lambda _c: commit())
        row.add_controller(focus)
        return self._with_reset(row, name)

    def _with_reset(self, row: Gtk.Widget, name: str) -> Gtk.Widget:
        button = Gtk.Button(icon_name="edit-undo-symbolic")
        button.set_valign(Gtk.Align.CENTER)
        button.add_css_class("flat")
        button.set_tooltip_text(t("Remove the override and restore the configured default"))
        button.connect("clicked", lambda _b: self._reset(name))
        try:
            row.add_suffix(button)
        except AttributeError:
            pass
        return row

    def _save(self, name: str, value) -> None:
        if not self.backend.set(name, value, label=f"{name} = {value}"):
            if self.main_window is not None:
                self.main_window.add_toast(Adw.Toast.new(t("Could not apply {name}").format(name=name)))
            return
        if hasattr(self.main_window, "preview_changed"):
            self.main_window.preview_changed(f"{name} = {value}")

    def _schedule_save(self, name: str, value) -> None:
        # SpinRow changes fire rapidly; reuse the list's debounce key.
        key = f"option:{name}"
        timer = getattr(self, "_spin_timers", {}).pop(key, None) if hasattr(self, "_spin_timers") else None
        if timer:
            GLib.source_remove(timer)
        if not hasattr(self, "_spin_timers"):
            self._spin_timers: dict[str, int] = {}

        def run() -> bool:
            self._spin_timers.pop(key, None)
            self._save(name, value)
            return False

        self._spin_timers[key] = GLib.timeout_add(350, run)

    def _reset(self, name: str) -> None:
        if self.backend.reset(name):
            subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
            self._rebuild()
