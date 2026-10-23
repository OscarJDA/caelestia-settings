"""Declarative GTK settings engine.

A page is built from :mod:`src.settings_schema` data.  The same widgets are
used for Caelestia (shell.json) and Hyprland (override layer) settings, which
keeps behaviour, search and undo consistent across the app.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from src.safe_io import HISTORY, atomic_write_json, read_json  # noqa: E402
from src.settings_core import delete_path, get_path, set_path  # noqa: E402
from src.lang import t  # noqa: E402
from src.settings_schema import Expander, Group, Option, PageSpec  # noqa: E402

_MISSING = object()


class ShellBackend:
    """Read/write nested keys in a Caelestia ``shell.json`` file."""

    def __init__(self, path, error_sink: Callable[[str], None] | None = None) -> None:
        self.path = path
        self.error_sink = error_sink

    def available(self, key: str) -> bool:
        return True

    def get(self, key: str, kind: str | None = None, default=None):
        return get_path(read_json(self.path, {}), key, default)

    def set(self, key: str, value, label: str | None = None, record: bool = True) -> bool:
        data = read_json(self.path, {})
        old = get_path(data, key, _MISSING)
        if old is not _MISSING and old == value:
            return True
        old_snapshot = copy.deepcopy(old) if old is not _MISSING else _MISSING
        value_snapshot = copy.deepcopy(value)
        set_path(data, key, value)
        atomic_write_json(self.path, data)

        if record:
            def undo() -> None:
                current = read_json(self.path, {})
                if old_snapshot is _MISSING:
                    delete_path(current, key)
                else:
                    set_path(current, key, copy.deepcopy(old_snapshot))
                atomic_write_json(self.path, current)

            def redo() -> None:
                current = read_json(self.path, {})
                set_path(current, key, copy.deepcopy(value_snapshot))
                atomic_write_json(self.path, current)

            HISTORY.push(label or f"{key} = {value}", undo, redo)
        return True

    def _error(self, message: str) -> None:
        print(f"Shell settings: {message}")
        if self.error_sink:
            self.error_sink(message)


class OverlayShellBackend(ShellBackend):
    """Per-monitor overlay: read the monitor file, fall back to the global one.

    Writes always go to the per-monitor file, so touching a value creates an
    override while untouched values keep following the global configuration.
    """

    def __init__(self, path, fallback_path, error_sink: Callable[[str], None] | None = None) -> None:
        super().__init__(path, error_sink=error_sink)
        self.fallback_path = fallback_path

    def get(self, key: str, kind: str | None = None, default=None):
        value = get_path(read_json(self.path, {}), key, _MISSING)
        if value is not _MISSING:
            return value
        return get_path(read_json(self.fallback_path, {}), key, default)


@dataclass
class BoundRow:
    option: Option
    row: Gtk.Widget
    update: Callable[[object], None]


@dataclass
class SearchEntry:
    page_id: str
    page_title: str
    label: str
    subtitle: str
    keywords: str
    row: Gtk.Widget | None = None


class JsonFileBackend:
    """Backend for JSON documents that are not ``shell.json``.

    Used by editors whose data is rendered elsewhere (Hyprland gesture lists,
    advanced window rules, ...). ``on_change`` runs after every write and after
    undo/redo so the caller can regenerate/apply its target file.
    """

    def __init__(self, path, default: dict | None = None, on_change=None, error_sink=None) -> None:
        self.path = path
        self.default = copy.deepcopy(default or {})
        self.on_change = on_change
        self.error_sink = error_sink

    def available(self, key: str) -> bool:
        return True

    def _read(self) -> dict:
        data = read_json(self.path, copy.deepcopy(self.default))
        return data if data else copy.deepcopy(self.default)

    def get(self, key: str, kind: str | None = None, default=None):
        return get_path(self._read(), key, default)

    def mutate(self, mutator, label: str | None = None, record: bool = True) -> bool:
        """Apply ``mutator(data)`` to the whole document and save it.

        Used for structural edits (adding, removing or reordering entries)
        where there is no single dotted path to write.
        """
        data = self._read()
        before = copy.deepcopy(data)
        mutator(data)
        if data == before:
            return False
        after = copy.deepcopy(data)
        atomic_write_json(self.path, data)
        self._changed()
        if record:
            def undo() -> None:
                atomic_write_json(self.path, copy.deepcopy(before))
                self._changed()

            def redo() -> None:
                atomic_write_json(self.path, copy.deepcopy(after))
                self._changed()

            HISTORY.push(label or t("Widgets updated"), undo, redo)
        return True

    def set(self, key: str, value, label: str | None = None, record: bool = True) -> bool:
        data = self._read()
        old = get_path(data, key, _MISSING)
        if old is not _MISSING and old == value:
            return True
        old_snapshot = copy.deepcopy(old) if old is not _MISSING else _MISSING
        value_snapshot = copy.deepcopy(value)
        set_path(data, key, value)
        atomic_write_json(self.path, data)
        self._changed()
        if record:
            def undo() -> None:
                current = self._read()
                if old_snapshot is _MISSING:
                    delete_path(current, key)
                else:
                    set_path(current, key, copy.deepcopy(old_snapshot))
                atomic_write_json(self.path, current)
                self._changed()

            def redo() -> None:
                current = self._read()
                set_path(current, key, copy.deepcopy(value_snapshot))
                atomic_write_json(self.path, current)
                self._changed()

            HISTORY.push(label or t("{name} updated").format(name=key), undo, redo)
        return True

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception as exc:
                print(f"JSON backend on_change failed: {exc}")
                if self.error_sink:
                    self.error_sink(str(exc))


def apply_search_highlight(widget: Gtk.Widget) -> None:
    if widget is None:
        return
    widget.add_css_class("search-highlight")
    try:
        widget.grab_focus()
    except Exception:
        pass

    def clear() -> bool:
        widget.remove_css_class("search-highlight")
        return False

    GLib.timeout_add(1800, clear)


class SettingsPage(Adw.PreferencesPage):
    """A preferences page generated from a :class:`PageSpec`."""

    def __init__(
        self,
        main_window,
        spec: PageSpec,
        backend,
        custom_builders: list[Callable[["SettingsPage"], None]] | None = None,
    ) -> None:
        super().__init__()
        self.main_window = main_window
        self.spec = spec
        self.backend = backend
        self.page_id = spec.page_id
        self.page_title = t(spec.title)
        self._bound: list[BoundRow] = []
        self._extra_search: list[SearchEntry] = []
        self._refresh_callbacks: list[Callable[[], None]] = []
        self._timers: dict[str, int] = {}
        self._loading = False

        top_expanders = [item for item in spec.groups if isinstance(item, Expander)]
        for group_spec in spec.groups:
            if not isinstance(group_spec, Expander):
                self._build_group(group_spec)
        if top_expanders:
            layout_group = Adw.PreferencesGroup(title=t("Layout-specific options"))
            built = sum(self._build_row(item, layout_group, None) for item in top_expanders)
            if built:
                self.add(layout_group)

        for builder in custom_builders or []:
            builder(self)

    # ── Building ──────────────────────────────────────────────────────────

    def _build_group(self, group_spec: Group) -> None:
        group = Adw.PreferencesGroup(title=t(group_spec.title))
        if group_spec.description:
            group.set_description(t(group_spec.description))
        built = sum(self._build_row(row_spec, group, None) for row_spec in group_spec.rows)
        if built:
            self.add(group)

    def _build_row(self, spec, group: Adw.PreferencesGroup, expander: Adw.ExpanderRow | None) -> int:
        if isinstance(spec, Expander):
            container = Adw.ExpanderRow(title=t(spec.title))
            if spec.subtitle:
                container.set_subtitle(t(spec.subtitle))
            built = sum(self._build_row(child, group, container) for child in spec.rows)
            if built:
                group.add(container)
                return 1
            return 0

        if not isinstance(spec, Option):
            return 0

        built = self._create_option_row(spec)
        if built is None:
            return 0
        row, update = built
        if expander is not None:
            expander.add_row(row)
        else:
            group.add(row)
        self._bound.append(BoundRow(spec, row, update))
        return 1

    def _create_option_row(self, option: Option):
        if hasattr(self.backend, "available") and not self.backend.available(option.key):
            return None

        value = self.backend.get(option.key, kind=option.kind, default=option.default)
        if value is None:
            value = option.default

        subtitle = t(option.subtitle) if option.subtitle else option.subtitle
        if option.unit:
            subtitle = f"{subtitle} ({option.unit})" if subtitle else option.unit

        if option.kind == "bool":
            return self._build_bool(option, subtitle, bool(value))
        if option.kind in ("int", "float"):
            return self._build_number(option, subtitle, value)
        if option.kind == "enum":
            return self._build_enum(option, subtitle, value)
        if option.kind == "string":
            return self._build_string(option, subtitle, value)
        if option.kind == "font":
            return self._build_font(option, subtitle, value)
        print(f"Unknown setting kind: {option.kind}")
        return None

    def _build_bool(self, option: Option, subtitle: str, value: bool):
        row = Adw.SwitchRow(title=t(option.label), subtitle=subtitle or None)
        row.set_active(value)

        def on_toggle(widget, _pspec):
            if self._loading:
                return
            self._save(option, widget.get_active())

        handler = row.connect("notify::active", on_toggle)

        def update(new_value) -> None:
            row.handler_block(handler)
            row.set_active(bool(new_value))
            row.handler_unblock(handler)

        return row, update

    def _build_number(self, option: Option, subtitle: str, value):
        row = Adw.SpinRow.new_with_range(option.minimum, option.maximum, option.step)
        row.set_title(t(option.label))
        if subtitle:
            row.set_subtitle(subtitle)
        row.set_digits(option.digits)
        row.set_value(float(value))

        def on_change(widget, _pspec):
            if self._loading:
                return
            self._schedule(
                option.key,
                lambda: self._save(option, widget.get_value(), row=widget),
                delay=350,
            )

        row.connect("notify::value", on_change)

        def update(new_value) -> None:
            row.set_value(float(new_value))

        return row, update

    def _build_enum(self, option: Option, subtitle: str, value):
        row = Adw.ComboRow(title=t(option.label), subtitle=subtitle or None)
        labels = Gtk.StringList.new([t(label) for _val, label in option.choices])
        row.set_model(labels)
        values = [val for val, _label in option.choices]
        try:
            index = values.index(value)
        except ValueError:
            index = 0
        row.set_selected(index)

        def on_select(widget, _pspec):
            if self._loading:
                return
            selected = widget.get_selected()
            if 0 <= selected < len(values):
                self._save(option, values[selected])

        row.connect("notify::selected", on_select)

        def update(new_value) -> None:
            try:
                row.set_selected(values.index(new_value))
            except ValueError:
                row.set_selected(0)

        return row, update

    def _build_string(self, option: Option, subtitle: str, value):
        row = Adw.EntryRow(title=t(option.label))
        if subtitle:
            row.set_tooltip_text(subtitle)
        row.set_show_apply_button(True)
        row.set_text("" if value is None else str(value))

        def commit(_widget=None) -> None:
            if self._loading:
                return
            self._save(option, row.get_text())

        row.connect("apply", commit)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", lambda _c: commit())
        row.add_controller(focus)

        def update(new_value) -> None:
            row.set_text("" if new_value is None else str(new_value))

        return row, update

    def _build_font(self, option: Option, subtitle: str, value):
        row = Adw.ActionRow(title=t(option.label), subtitle=subtitle or None)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)

        button = Gtk.FontDialogButton()
        button.set_valign(Gtk.Align.CENTER)
        button.set_level(Gtk.FontLevel.FAMILY)
        button.set_use_font(True)
        if value:
            button.set_font_desc(Pango.FontDescription.from_string(str(value)))
        box.append(button)

        clear = Gtk.Button(icon_name="edit-clear-symbolic")
        clear.set_valign(Gtk.Align.CENTER)
        clear.set_tooltip_text(t("Use the inherited default"))
        box.append(clear)
        row.add_suffix(box)

        def current_family() -> str:
            desc = button.get_font_desc()
            return (desc.get_family() or "") if desc is not None else ""

        def on_font(_button, _pspec=None):
            if self._loading:
                return
            self._save(option, current_family())

        button.connect("notify::font-desc", on_font)

        def on_clear(_button):
            if self._loading:
                return
            self._loading = True
            try:
                button.set_font_desc(Pango.FontDescription.from_string(""))
            finally:
                self._loading = False
            self._save(option, "")

        clear.connect("clicked", on_clear)

        def update(new_value) -> None:
            button.set_font_desc(Pango.FontDescription.from_string(str(new_value or "")))

        return row, update

    # ── Saving / refreshing ───────────────────────────────────────────────

    def _save(self, option: Option, value, row=None) -> None:
        # Adw.SpinRow always stores doubles; Hyprland rejects 1.0 for integer
        # options ("integer type requires a bool or an integer").
        if option.kind == "int":
            value = int(round(value))
        elif option.kind == "float":
            value = float(value)
        if not self.backend.set(option.key, value, label=f"{t(option.label)}: {value}"):
            if self.main_window is not None and hasattr(self.main_window, "add_toast"):
                self.main_window.add_toast(Adw.Toast.new(t("Could not apply {name}").format(name=t(option.label))))
            return
        if self.main_window is not None and hasattr(self.main_window, "preview_changed"):
            self.main_window.preview_changed(f"{t(option.label)}: {value}")

    def _schedule(self, key: str, callback: Callable[[], None], delay: int = 350) -> None:
        old_timer = self._timers.pop(key, None)
        if old_timer:
            GLib.source_remove(old_timer)

        def run() -> bool:
            self._timers.pop(key, None)
            callback()
            return False

        self._timers[key] = GLib.timeout_add(delay, run)

    def reload_values(self) -> None:
        """Re-read every value from the backend (used after undo/redo)."""
        for timer in list(self._timers.values()):
            GLib.source_remove(timer)
        self._timers.clear()
        self._loading = True
        try:
            for bound in self._bound:
                value = self.backend.get(bound.option.key, kind=bound.option.kind, default=bound.option.default)
                if value is None:
                    value = bound.option.default
                try:
                    bound.update(value)
                except Exception as exc:
                    print(f"Could not refresh {bound.option.key}: {exc}")
            for callback in self._refresh_callbacks:
                try:
                    callback()
                except Exception as exc:
                    print(f"Refresh callback failed: {exc}")
        finally:
            self._loading = False

    def add_refresh_callback(self, callback: Callable[[], None]) -> None:
        self._refresh_callbacks.append(callback)

    # ── Search ────────────────────────────────────────────────────────────

    def register_search(
        self,
        label: str,
        subtitle: str = "",
        keywords: str = "",
        row: Gtk.Widget | None = None,
    ) -> None:
        self._extra_search.append(
            SearchEntry(self.page_id, self.page_title, t(label), t(subtitle), keywords, row)
        )

    def search_items(self) -> list[SearchEntry]:
        items = [
            SearchEntry(
                self.page_id,
                self.page_title,
                t(bound.option.label),
                t(bound.option.subtitle) if bound.option.subtitle else bound.option.subtitle,
                bound.option.search_text(),
                bound.row,
            )
            for bound in self._bound
        ]
        items.extend(self._extra_search)
        return items

    def highlight(self, row: Gtk.Widget | None) -> None:
        apply_search_highlight(row)


# ── Small shared helpers ────────────────────────────────────────────────────


def make_backend_error_toast(main_window):
    def sink(message: str) -> None:
        if main_window is not None and hasattr(main_window, "add_toast"):
            main_window.add_toast(Adw.Toast.new(message))

    return sink
