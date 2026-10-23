"""Desktop widgets configuration for the Caelestia shell fork.

Widgets are rendered by ``DesktopWidgets.qml`` in the shell.  Instances live in
``desktop_widgets.json`` (format v2): each entry has a stable id, a type from
``widget_catalog``, a corner, an order, a scale and type-specific options.

The old four-slot format (v1) is migrated automatically the first time this
page is opened.
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
from src.widget_catalog import (
    ACCENTS,
    CARD_STYLES,
    CORNERS,
    WIDGETS,
    default_config,
    default_instance,
    migrate_v1,
)

DESKTOP_WIDGETS_FILE = Path.home() / ".config" / "caelestia-settings" / "desktop_widgets.json"

CORNER_LABELS = dict(CORNERS)
CORNER_ORDER = {value: index for index, (value, _label) in enumerate(CORNERS)}


class DesktopWidgetsPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._loading = False
        self._bindings: list[tuple] = []
        self._groups: list[Adw.PreferencesGroup] = []
        self.shell = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        self.widgets = JsonFileBackend(
            DESKTOP_WIDGETS_FILE,
            default_config(),
            error_sink=make_backend_error_toast(main_window),
        )
        self._ensure_v2()
        self._build()

    # ── Migration ───────────────────────────────────────────────────────────

    def _ensure_v2(self) -> None:
        data = self.widgets._read()
        if data.get("version") == 2:
            return

        migrated = migrate_v1(data)

        def apply(target: dict) -> None:
            target.clear()
            target.update(migrated)

        self.widgets.mutate(apply, "Migrated desktop widgets", record=False)

    # ── Generic rows ────────────────────────────────────────────────────────

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

    # ── Building ────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._loading = True
        try:
            for group in self._groups:
                self.remove(group)
            self._groups = []
            self._bindings.clear()
            self._build_appearance()
            self._build_instances()
            self._build_native()
        finally:
            self._loading = False

    def _add_group(self, group) -> None:
        self._groups.append(group)
        self.add(group)

    def _build_appearance(self) -> None:
        group = Adw.PreferencesGroup(
            title=t("Widget appearance"),
            description=t(
                "Material cards drawn above the wallpaper. Changes apply immediately in the shell."
            ),
        )

        style = Adw.ActionRow(title=t("Card style"))
        combo = Gtk.ComboBoxText()
        combo.set_valign(Gtk.Align.CENTER)
        for value, label in CARD_STYLES:
            combo.append(value, t(label))
        combo.set_active_id(str(self.widgets.get("global.cardStyle", default="material")))
        if combo.get_active_id() is None:
            combo.set_active(0)
        self._bindings.append((combo, self.widgets, "global.cardStyle", "material", "combo"))

        def on_style(widget):
            if not self._loading:
                value = widget.get_active_id()
                if value is not None:
                    self.widgets.set("global.cardStyle", value)

        combo.connect("changed", on_style)
        style.add_suffix(combo)
        group.add(style)

        self._combo(
            group,
            self.widgets,
            "global.accent",
            "Accent colour",
            ACCENTS,
            "auto",
        )
        self._number(
            group,
            self.widgets,
            "global.opacity",
            "Card opacity",
            1.0,
            0.0,
            1.0,
            0.05,
            2,
        )
        self._number(
            group,
            self.widgets,
            "global.edgeMargin",
            "Screen margin",
            28,
            0,
            200,
            2,
            0,
            "int",
        )
        self._number(
            group,
            self.widgets,
            "global.gap",
            "Gap between widgets",
            16,
            0,
            64,
            1,
            0,
            "int",
        )
        self._add_group(group)

    def _build_instances(self) -> None:
        data = self.widgets._read()
        instances = data.get("widgets")
        if not isinstance(instances, dict):
            instances = {}

        group = Adw.PreferencesGroup(
            title=t("Desktop widgets"),
            description=t("Add as many widgets as you like and place them in nine fixed zones."),
        )

        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.set_valign(Gtk.Align.CENTER)
        add_button.set_tooltip_text(t("Add widget"))
        add_button.connect("clicked", lambda _button: self._open_add_dialog())
        group.set_header_suffix(add_button)

        ordered = sorted(
            (
                (widget_id, widget)
                for widget_id, widget in instances.items()
                if isinstance(widget, dict) and widget.get("type") in WIDGETS
            ),
            key=lambda item: (
                CORNER_ORDER.get(item[1].get("corner"), 99),
                int(item[1].get("order") or 0),
                item[1].get("type", ""),
            ),
        )

        if not ordered:
            empty = Adw.ActionRow(
                title=t("No widgets yet"),
                subtitle=t("Use the + button to add your first widget."),
            )
            group.add(empty)

        for widget_id, widget in ordered:
            self._build_instance_row(group, widget_id, widget)

        self._add_group(group)

    def _build_instance_row(self, group, widget_id: str, widget: dict) -> None:
        widget_type = widget.get("type", "")
        meta = WIDGETS.get(widget_type, {})
        corner = widget.get("corner", meta.get("corner", "top-left"))
        scale = float(widget.get("scale") or 1.0)
        enabled = widget.get("enabled", True) is not False

        expander = Adw.ExpanderRow(
            title=t(meta.get("name", widget_type)),
            subtitle=f"{t(CORNER_LABELS.get(corner, corner))} · {round(scale * 100)} %",
        )
        expander.set_icon_name("preferences-desktop-display-symbolic")

        toggle = Gtk.Switch()
        toggle.set_valign(Gtk.Align.CENTER)
        toggle.set_active(enabled)
        toggle.set_tooltip_text(t("Show widget"))
        toggle.connect(
            "notify::active",
            lambda switch, _pspec: self._set_enabled(widget_id, switch.get_active()),
        )
        expander.add_suffix(toggle)

        group.add(expander)

        # Placement ────────────────────────────────────────────────────────
        corner_row = Adw.ComboRow(
            title=t("Zone"),
            model=Gtk.StringList.new([t(label) for _value, label in CORNERS]),
        )
        corner_index = CORNER_ORDER.get(corner, 0)
        corner_row.set_selected(corner_index)
        _, corner_labels = zip(*CORNERS)

        def on_corner(row, _pspec):
            if self._loading:
                return
            selected = row.get_selected()
            if 0 <= selected < len(CORNERS):
                self.widgets.set(f"widgets.{widget_id}.corner", CORNERS[selected][0])
                subtitle = f"{t(CORNER_LABELS.get(CORNERS[selected][0], CORNERS[selected][0]))} · {round(scale_row.get_value() * 100)} %"
                expander.set_subtitle(subtitle)

        corner_row.connect("notify::selected", on_corner)
        expander.add_row(corner_row)

        scale_row = Adw.SpinRow.new_with_range(0.5, 3.0, 0.05)
        scale_row.set_title(t("Scale"))
        scale_row.set_digits(2)
        scale_row.set_value(scale)

        def on_scale(row, _pspec):
            if self._loading:
                return
            self.widgets.set(f"widgets.{widget_id}.scale", round(row.get_value(), 2))
            selected = corner_row.get_selected()
            corner_value = CORNERS[selected][0] if 0 <= selected < len(CORNERS) else corner
            subtitle = f"{t(CORNER_LABELS.get(corner_value, corner_value))} · {round(row.get_value() * 100)} %"
            expander.set_subtitle(subtitle)

        scale_row.connect("notify::value", on_scale)
        expander.add_row(scale_row)

        actions_row = Adw.ActionRow(title=t("Arrange"))
        up = Gtk.Button(icon_name="go-up-symbolic")
        up.set_valign(Gtk.Align.CENTER)
        up.set_tooltip_text(t("Move up"))
        up.connect("clicked", lambda _button: self._move(widget_id, -1))
        down = Gtk.Button(icon_name="go-down-symbolic")
        down.set_valign(Gtk.Align.CENTER)
        down.set_tooltip_text(t("Move down"))
        down.connect("clicked", lambda _button: self._move(widget_id, 1))
        duplicate = Gtk.Button(icon_name="edit-copy-symbolic")
        duplicate.set_valign(Gtk.Align.CENTER)
        duplicate.set_tooltip_text(t("Duplicate"))
        duplicate.connect("clicked", lambda _button: self._duplicate(widget_id))
        delete = Gtk.Button(icon_name="user-trash-symbolic")
        delete.set_valign(Gtk.Align.CENTER)
        delete.add_css_class("destructive-action")
        delete.set_tooltip_text(t("Remove"))
        delete.connect("clicked", lambda _button: self._remove(widget_id))
        actions_row.add_suffix(up)
        actions_row.add_suffix(down)
        actions_row.add_suffix(duplicate)
        actions_row.add_suffix(delete)
        expander.add_row(actions_row)

        # Type-specific options ────────────────────────────────────────────
        options = widget.get("options")
        if not isinstance(options, dict):
            options = {}

        for key, option in meta.get("options", {}).items():
            value = options.get(key, option.get("default"))
            self._build_option_row(expander, widget_id, key, option, value)

    def _build_option_row(self, expander, widget_id: str, key: str, option: dict, value) -> None:
        path = f"widgets.{widget_id}.options.{key}"
        kind = option.get("kind", "text")
        title = t(option.get("label", key))

        if kind == "bool":
            row = Adw.SwitchRow(title=title)
            row.set_active(bool(value))
            row.connect(
                "notify::active",
                lambda switch, _pspec: self._set_option(path, switch.get_active()),
            )
            expander.add_row(row)
            return

        if kind in ("int", "float"):
            digits = 0 if kind == "int" else int(option.get("digits", 2))
            row = Adw.SpinRow.new_with_range(
                float(option.get("min", 0)),
                float(option.get("max", 100)),
                float(option.get("step", 1)),
            )
            row.set_title(title)
            row.set_digits(digits)
            row.set_value(float(value))
            row.connect(
                "notify::value",
                lambda spin, _pspec: self._set_option(
                    path,
                    int(round(spin.get_value())) if kind == "int" else round(spin.get_value(), digits),
                ),
            )
            expander.add_row(row)
            return

        if kind == "choice":
            choices = option.get("choices", ())
            row = Adw.ComboRow(
                title=title,
                model=Gtk.StringList.new([t(label) for _choice_value, label in choices]),
            )
            values = [choice_value for choice_value, _label in choices]
            try:
                row.set_selected(values.index(value))
            except ValueError:
                row.set_selected(0)

            def on_choice(combo, _pspec, values=values):
                selected = combo.get_selected()
                if 0 <= selected < len(values):
                    self._set_option(path, values[selected])

            row.connect("notify::selected", on_choice)
            expander.add_row(row)
            return

        row = Adw.EntryRow(title=title)
        row.set_text("" if value is None else str(value))
        if option.get("placeholder"):
            row.set_tooltip_text(option["placeholder"])
        row.connect("changed", lambda entry: self._set_option(path, entry.get_text()))
        expander.add_row(row)

    def _build_native(self) -> None:
        clock = Adw.PreferencesGroup(
            title=t("Native desktop clock"),
            description=t("Large clock drawn behind windows by Caelestia itself."),
        )
        self._switch(clock, self.shell, "background.desktopClock.enabled", "Show clock", False)
        self._combo(
            clock,
            self.shell,
            "background.desktopClock.position",
            "Position",
            CORNERS,
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
        self._switch(clock, self.shell, "background.desktopClock.invertColors", "Invert colours", False)
        self._switch(clock, self.shell, "background.desktopClock.background.enabled", "Background", False)
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
        self._switch(clock, self.shell, "background.desktopClock.background.blur", "Blur background", True)
        self._switch(clock, self.shell, "background.desktopClock.shadow.enabled", "Shadow", True)
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
        self._add_group(clock)

        visualiser = Adw.PreferencesGroup(
            title=t("Native audio visualiser"),
            description=t("Visualiser drawn behind desktop windows."),
        )
        self._switch(visualiser, self.shell, "background.visualiser.enabled", "Enable visualiser", False)
        self._switch(
            visualiser,
            self.shell,
            "background.visualiser.autoHide",
            "Auto-hide",
            True,
            "Hide when there are no floating windows",
        )
        self._switch(visualiser, self.shell, "background.visualiser.blur", "Blur wallpaper", False)
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
        self._add_group(visualiser)

    # ── Structural edits ────────────────────────────────────────────────────

    def _set_enabled(self, widget_id: str, enabled: bool) -> None:
        if self._loading:
            return
        self.widgets.set(f"widgets.{widget_id}.enabled", bool(enabled))

    def _set_option(self, path: str, value) -> None:
        if self._loading:
            return
        self.widgets.set(path, value)

    def _next_id(self, widget_type: str, widgets: dict) -> str:
        index = 1
        while f"{widget_type}-{index}" in widgets:
            index += 1
        return f"{widget_type}-{index}"

    def _siblings(self, widgets: dict, corner: str, exclude: str) -> list[str]:
        return sorted(
            (
                widget_id
                for widget_id, widget in widgets.items()
                if isinstance(widget, dict)
                and widget_id != exclude
                and widget.get("corner", WIDGETS.get(widget.get("type", ""), {}).get("corner")) == corner
            ),
            key=lambda widget_id: int(widgets[widget_id].get("order") or 0),
        )

    def _move(self, widget_id: str, direction: int) -> None:
        data = self.widgets._read()
        widgets = data.get("widgets")
        if not isinstance(widgets, dict) or widget_id not in widgets:
            return
        widget = widgets[widget_id]
        corner = widget.get("corner", "top-left")
        siblings = self._siblings(widgets, corner, widget_id)
        siblings.append(widget_id)
        siblings.sort(key=lambda item: (int(widgets[item].get("order") or 0), item == widget_id))

        index = siblings.index(widget_id)
        target = index + direction
        if target < 0 or target >= len(siblings):
            return
        siblings[index], siblings[target] = siblings[target], siblings[index]

        def apply(target_data: dict) -> None:
            target_widgets = target_data.setdefault("widgets", {})
            for order, item in enumerate(siblings):
                if isinstance(target_widgets.get(item), dict):
                    target_widgets[item]["order"] = order

        self.widgets.mutate(apply, "Reordered desktop widgets")
        self._build()

    def _duplicate(self, widget_id: str) -> None:
        data = self.widgets._read()
        widgets = data.get("widgets")
        if not isinstance(widgets, dict) or widget_id not in widgets:
            return
        source = widgets[widget_id]
        widget_type = source.get("type")
        if widget_type not in WIDGETS:
            return
        corner = source.get("corner", WIDGETS[widget_type]["corner"])
        siblings = self._siblings(widgets, corner, widget_id)
        base_order = int(source.get("order") or 0)
        order = base_order + 1

        def apply(target_data: dict) -> None:
            target_widgets = target_data.setdefault("widgets", {})
            new_id = self._next_id(widget_type, target_widgets)
            for item in siblings:
                if not isinstance(target_widgets.get(item), dict):
                    continue
                current = int(target_widgets[item].get("order") or 0)
                if current >= order:
                    target_widgets[item]["order"] = current + 1
            copy = {
                "type": widget_type,
                "enabled": source.get("enabled", True),
                "corner": corner,
                "order": order,
                "scale": source.get("scale", 1.0),
                "options": dict(source.get("options") or {}),
            }
            target_widgets[new_id] = copy

        self.widgets.mutate(apply, "Duplicated desktop widget")
        self._build()

    def _remove(self, widget_id: str) -> None:
        def apply(target_data: dict) -> None:
            target_widgets = target_data.get("widgets")
            if isinstance(target_widgets, dict):
                target_widgets.pop(widget_id, None)

        self.widgets.mutate(apply, "Removed desktop widget")
        self._build()

    def _add(self, widget_type: str) -> None:
        if widget_type not in WIDGETS:
            return
        meta = WIDGETS[widget_type]
        corner = meta["corner"]

        def apply(target_data: dict) -> None:
            target_widgets = target_data.setdefault("widgets", {})
            siblings = self._siblings(target_widgets, corner, "")
            order = max(
                (int(target_widgets[item].get("order") or 0) for item in siblings),
                default=-1,
            ) + 1
            target_widgets[self._next_id(widget_type, target_widgets)] = default_instance(
                widget_type, corner, order
            )

        self.widgets.mutate(apply, "Added desktop widget")
        self._build()

    # ── Add dialog ──────────────────────────────────────────────────────────

    def _open_add_dialog(self) -> None:
        dialog = Adw.Dialog()
        dialog.set_title(t("Add widget"))
        dialog.set_content_width(420)
        dialog.set_content_height(560)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        toolbar.add_top_bar(header)

        search = Gtk.SearchEntry()
        search.set_placeholder_text(t("Search widgets"))
        search.set_margin_top(8)
        search.set_margin_bottom(8)
        search.set_margin_start(12)
        search.set_margin_end(12)
        toolbar.add_top_bar(search)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        listbox.set_margin_top(8)
        listbox.set_margin_bottom(12)
        listbox.set_margin_start(12)
        listbox.set_margin_end(12)

        rows = []
        for widget_type, meta in sorted(WIDGETS.items(), key=lambda item: item[1]["name"].lower()):
            row = Adw.ActionRow(
                title=t(meta["name"]),
                subtitle=t(CORNER_LABELS.get(meta["corner"], meta["corner"])),
            )
            row.set_activatable(True)
            row.connect("activated", self._make_activate(widget_type, dialog))
            listbox.append(row)
            rows.append((row, t(meta["name"]).lower(), widget_type))

        def on_search(entry):
            query = entry.get_text().strip().lower()
            for row, name, _widget_type in rows:
                row.set_visible(query == "" or query in name)

        search.connect("search-changed", on_search)

        scroller = Gtk.ScrolledWindow()
        scroller.set_child(listbox)
        scroller.set_vexpand(True)
        toolbar.set_content(scroller)

        dialog.set_child(toolbar)
        dialog.present(self)

    def _make_activate(self, widget_type: str, dialog: Adw.Dialog):
        def activate(_row) -> None:
            self._add(widget_type)
            dialog.close()

        return activate

    # ── Reload ──────────────────────────────────────────────────────────────

    def reload_values(self) -> None:
        self._build()
