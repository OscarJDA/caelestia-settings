"""Reusable list editors for the declarative settings pages.

These cover the Caelestia bar lists (entries, status icons, icon rules) and
plain string lists.  All of them read/write through the same backend as the
scalar rows, so undo/redo and backups work identically.
"""

from __future__ import annotations

import copy
import shlex
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk  # noqa: E402

from src.lang import t  # noqa: E402


def _entry_row(label: str, value: str, on_apply: Callable[[str], None], subtitle: str = "") -> Adw.EntryRow:
    row = Adw.EntryRow(title=t(label))
    row.set_text(value or "")
    if subtitle:
        row.set_tooltip_text(t(subtitle))
    row.set_show_apply_button(True)

    def commit(_widget=None) -> None:
        on_apply(row.get_text())

    row.connect("apply", commit)
    focus = Gtk.EventControllerFocus.new()
    focus.connect("leave", lambda _c: commit())
    row.add_controller(focus)
    return row


def _small_button(icon: str, tooltip: str, callback) -> Gtk.Button:
    button = Gtk.Button(icon_name=icon)
    button.set_valign(Gtk.Align.CENTER)
    button.set_tooltip_text(t(tooltip))
    button.add_css_class("flat")
    button.connect("clicked", callback)
    return button


def _drag_handle() -> Gtk.Image:
    image = Gtk.Image.new_from_icon_name("list-drag-handle-symbolic")
    image.set_valign(Gtk.Align.CENTER)
    image.add_css_class("dim-label")
    image.set_tooltip_text(t("Drag to reorder"))
    return image


class ReorderableIdList(Adw.PreferencesGroup):
    """Editor for Caelestia's ``[{id, enabled}, ...]`` lists."""

    def __init__(
        self,
        page,
        backend,
        key: str,
        defaults: list[dict],
        choices: tuple[tuple[str, str], ...],
        title: str,
        description: str = "",
        allow_duplicates: bool = False,
    ) -> None:
        super().__init__(title=t(title), description=t(description) if description else None)
        self.page = page
        self.backend = backend
        self.key = key
        self.choices = dict(choices)
        self.allow_duplicates = allow_duplicates
        self.defaults = copy.deepcopy(defaults)
        self.items = self._load(defaults)
        self._rows: list[Gtk.Widget] = []
        self._rebuild()
        page.add_refresh_callback(self.reload)

    def _load(self, defaults: list[dict]) -> list[dict]:
        data = self.backend.get(self.key, default=None)
        if not isinstance(data, list):
            data = copy.deepcopy(defaults)
        cleaned = []
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                cleaned.append({"id": str(item["id"]), "enabled": bool(item.get("enabled", True))})
        return cleaned

    def reload(self) -> None:
        self.items = self._load(self.defaults)
        self._rebuild()

    def _save(self) -> None:
        self.backend.set(self.key, self.items, label=t("{name} updated").format(name=self.get_title()))

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        self._clear()
        for index, item in enumerate(self.items):
            row = self._make_row(index, item)
            self.add(row)
            self._rows.append(row)
        add_row = self._make_add_row()
        self.add(add_row)
        self._rows.append(add_row)

    def _make_row(self, index: int, item: dict) -> Adw.ActionRow:
        name = t(self.choices.get(item["id"], item["id"]))
        row = Adw.ActionRow(title=name, subtitle=f"id: {item['id']}")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_valign(Gtk.Align.CENTER)
        box.append(_drag_handle())
        box.append(_small_button("go-up-symbolic", t("Move up"), lambda _b: self._move(index, index - 1)))
        box.append(_small_button("go-down-symbolic", t("Move down"), lambda _b: self._move(index, index + 1)))

        toggle = Gtk.Switch()
        toggle.set_valign(Gtk.Align.CENTER)
        toggle.set_active(item.get("enabled", True))
        toggle.connect("notify::active", lambda sw, _p: self._toggle(index, sw.get_active()))
        box.append(toggle)
        box.append(_small_button("user-trash-symbolic", t("Remove"), lambda _b: self._remove(index)))

        row.add_suffix(box)
        row.set_activatable(False)

        source = Gtk.DragSource.new()
        source.set_actions(Gdk.DragAction.MOVE)
        source.connect("prepare", lambda _s, _x, _y, idx=index: Gdk.ContentProvider.new_for_value(str(idx)))
        row.add_controller(source)

        target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target.connect("drop", lambda _t, value, _x, _y, idx=index: self._drop(value, idx))
        row.add_controller(target)
        return row

    def _make_add_row(self) -> Adw.ActionRow:
        row = Adw.ActionRow(title=t("Add entry"))
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        labels = [t(label) for _key, label in self.choices.items()]
        dropdown = Gtk.DropDown.new_from_strings(labels)
        dropdown.set_valign(Gtk.Align.CENTER)
        box.append(dropdown)

        def add(_button) -> None:
            selected = dropdown.get_selected()
            keys = list(self.choices.keys())
            if 0 <= selected < len(keys):
                new_id = keys[selected]
                if not self.allow_duplicates and any(item["id"] == new_id for item in self.items):
                    return
                self.items.append({"id": new_id, "enabled": True})
                self._save()
                self._rebuild()

        box.append(_small_button("list-add-symbolic", t("Add"), add))
        row.add_suffix(box)
        row.set_activatable(False)
        return row

    def _toggle(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self.items):
            self.items[index]["enabled"] = enabled
            self._save()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._save()
            self._rebuild()

    def _move(self, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(self.items)):
            return
        target = max(0, min(target, len(self.items) - 1))
        item = self.items.pop(source)
        self.items.insert(target, item)
        self._save()
        self._rebuild()

    def _drop(self, value: str, target: int) -> bool:
        try:
            source = int(value)
        except (TypeError, ValueError):
            return False
        self._move(source, target)
        return True


class StringListEditor(Adw.PreferencesGroup):
    """Editor for simple ``["value", ...]`` lists."""

    def __init__(
        self,
        page,
        backend,
        key: str,
        defaults: list[str],
        title: str,
        description: str = "",
        placeholder: str = "Add value",
    ) -> None:
        super().__init__(title=t(title), description=t(description) if description else None)
        self.page = page
        self.backend = backend
        self.key = key
        self.defaults = list(defaults)
        self.values = self._load()
        self._rows: list[Gtk.Widget] = []
        self._placeholder = placeholder
        self._rebuild()
        page.add_refresh_callback(self.reload)

    def _load(self) -> list[str]:
        data = self.backend.get(self.key, default=None)
        if not isinstance(data, list):
            data = list(self.defaults)
        return [str(item) for item in data if str(item)]

    def reload(self) -> None:
        self.values = self._load()
        self._rebuild()

    def _save(self) -> None:
        self.backend.set(self.key, self.values, label=t("{name} updated").format(name=self.get_title()))

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        self._clear()
        for index, value in enumerate(self.values):
            row = Adw.ActionRow(title=value)
            row.add_suffix(_small_button("user-trash-symbolic", t("Remove"), lambda _b, i=index: self._remove(i)))
            self.add(row)
            self._rows.append(row)

        add = _entry_row(t(self._placeholder), "", self._add)
        self.add(add)
        self._rows.append(add)

    def _add(self, value: str) -> None:
        value = value.strip()
        if not value or value in self.values:
            return
        self.values.append(value)
        self._save()
        self._rebuild()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self.values):
            self.values.pop(index)
            self._save()
            self._rebuild()


class IconRuleEditor(Adw.PreferencesGroup):
    """Editor for Caelestia's icon rule lists (``name``/``regex``/``icon``)."""

    def __init__(
        self,
        page,
        backend,
        key: str,
        defaults: list[dict],
        title: str,
        description: str = "",
    ) -> None:
        super().__init__(title=t(title), description=t(description) if description else None)
        self.page = page
        self.backend = backend
        self.key = key
        self.defaults = copy.deepcopy(defaults)
        self.rules = self._load()
        self._rows: list[Gtk.Widget] = []
        self._rebuild()
        page.add_refresh_callback(self.reload)

    def _load(self) -> list[dict]:
        data = self.backend.get(self.key, default=None)
        if not isinstance(data, list):
            data = copy.deepcopy(self.defaults)
        cleaned = []
        for item in data:
            if not isinstance(item, dict):
                continue
            cleaned.append(
                {
                    "name": str(item.get("name", "")),
                    "regex": str(item.get("regex", "")),
                    "flags": str(item.get("flags", "")),
                    "icon": str(item.get("icon", "")),
                }
            )
        return cleaned

    def reload(self) -> None:
        self.rules = self._load()
        self._rebuild()

    def _save(self) -> None:
        payload = [
            {k: v for k, v in rule.items() if v}
            for rule in self.rules
        ]
        self.backend.set(self.key, payload, label=t("{name} updated").format(name=self.get_title()))

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        self._clear()
        for index, rule in enumerate(self.rules):
            expander = self._make_rule(index, rule)
            self.add(expander)
            self._rows.append(expander)
        add = Adw.ActionRow(title=t("Add rule"))
        add.add_suffix(_small_button("list-add-symbolic", t("Add rule"), lambda _b: self._add()))
        self.add(add)
        self._rows.append(add)

    def _make_rule(self, index: int, rule: dict) -> Adw.ExpanderRow:
        title = rule.get("name") or rule.get("regex") or t("(new rule)")
        expander = Adw.ExpanderRow(title=title, subtitle=f"{t('icon')}: {rule.get('icon') or '—'}")

        def update(field: str, value: str) -> None:
            rule[field] = value
            expander.set_title(rule.get("name") or rule.get("regex") or t("(new rule)"))
            expander.set_subtitle(f"{t('icon')}: {rule.get('icon') or '—'}")
            self._save()

        for field, label in (
            ("name", t("Name (exact match)")),
            ("regex", t("Regex")),
            ("flags", t("Regex flags")),
            ("icon", t("Material icon")),
        ):
            expander.add_row(_entry_row(label, rule.get(field, ""), lambda value, f=field: update(f, value)))

        remove = Adw.ActionRow(title=t("Remove rule"))
        remove.add_suffix(_small_button("user-trash-symbolic", t("Remove rule"), lambda _b, i=index: self._remove(i)))
        expander.add_row(remove)
        return expander

    def _add(self) -> None:
        self.rules.append({"name": "", "regex": "", "flags": "", "icon": ""})
        self._save()
        self._rebuild()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self.rules):
            self.rules.pop(index)
            self._save()
            self._rebuild()


def add_id_list(page, backend, key, defaults, choices, title, description="", allow_duplicates=False):
    editor = ReorderableIdList(
        page, backend, key, defaults, choices, title, description, allow_duplicates=allow_duplicates
    )
    page.add(editor)
    for choice_key, label in choices:
        page.register_search(label, title, f"{key} {choice_key}", None)
    return editor


def add_string_list(page, backend, key, defaults, title, description="", placeholder="Add value"):
    editor = StringListEditor(page, backend, key, defaults, title, description, placeholder)
    page.add(editor)
    page.register_search(title, description, key, editor)
    return editor


def add_icon_rules(page, backend, key, defaults, title, description=""):
    editor = IconRuleEditor(page, backend, key, defaults, title, description)
    page.add(editor)
    page.register_search(title, description, key, editor)
    return editor


# ── Generic object lists ────────────────────────────────────────────────────


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str = "string"  # string | command | action | bool | int | float | enum
    default: Any = ""
    choices: tuple[tuple[Any, str], ...] = ()
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    digits: int = 0
    subtitle: str = ""


def _format_command(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return shlex.join(str(part) for part in value)
    return "" if value is None else str(value)


def _parse_command(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return [text]


class ObjectListEditor(Adw.PreferencesGroup):
    """List-of-objects editor driven by :class:`FieldSpec` definitions.

    Used for launcher actions, VPN providers, idle timeouts, battery warnings
    and player aliases. Values are written back as the same JSON shape the
    Caelestia config expects (including command arrays).
    """

    def __init__(
        self,
        page,
        backend,
        key: str,
        defaults: list[dict],
        fields: list[FieldSpec],
        title: str,
        description: str = "",
        title_key: str = "name",
        new_item: dict | None = None,
        allow_reorder: bool = True,
    ) -> None:
        super().__init__(title=t(title), description=t(description) if description else None)
        self.page = page
        self.backend = backend
        self.key = key
        self.defaults = copy.deepcopy(defaults)
        self.fields = fields
        self.fields_by_key = {field.key: field for field in fields}
        self.title_key = title_key
        self.new_item = copy.deepcopy(new_item) if new_item else None
        self.allow_reorder = allow_reorder
        self.items = self._load()
        self._rows: list[Gtk.Widget] = []
        self._timers: dict[str, int] = {}
        self._rebuild()
        page.add_refresh_callback(self.reload)

    # ── Data ──────────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        data = self.backend.get(self.key, default=None)
        if not isinstance(data, list):
            data = copy.deepcopy(self.defaults)
        items = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            item = copy.deepcopy(raw)
            for field in self.fields:
                item.setdefault(field.key, copy.deepcopy(field.default))
            items.append(item)
        return items

    def reload(self) -> None:
        for timer in list(self._timers.values()):
            GLib.source_remove(timer)
        self._timers.clear()
        self.items = self._load()
        self._rebuild()

    def _save(self) -> None:
        self.backend.set(self.key, self.items, label=t("{name} updated").format(name=self.get_title()))

    def get_items(self) -> list[dict]:
        return self.items

    # ── UI ────────────────────────────────────────────────────────────────

    def _item_title(self, item: dict) -> str:
        value = item.get(self.title_key)
        if value:
            if isinstance(value, (list, tuple)):
                return _format_command(value)
            return str(value)
        for field in self.fields:
            if field.kind in ("string", "command", "action") and item.get(field.key):
                return _format_command(item[field.key])
        return t("New entry")

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        self._clear()
        for index, item in enumerate(self.items):
            expander = self._make_row(index, item)
            self.add(expander)
            self._rows.append(expander)
        add = Adw.ActionRow(title=t("Add entry"))
        add.add_suffix(_small_button("list-add-symbolic", t("Add entry"), lambda _b: self._add()))
        self.add(add)
        self._rows.append(add)

    def _make_row(self, index: int, item: dict) -> Adw.ExpanderRow:
        expander = Adw.ExpanderRow(title=self._item_title(item))

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_valign(Gtk.Align.CENTER)
        if self.allow_reorder:
            box.append(_small_button("go-up-symbolic", t("Move up"), lambda _b: self._move(index, index - 1)))
            box.append(_small_button("go-down-symbolic", t("Move down"), lambda _b: self._move(index, index + 1)))
        box.append(_small_button("user-trash-symbolic", t("Remove"), lambda _b: self._remove(index)))
        expander.add_suffix(box)

        for field in self.fields:
            row, _update = self._build_field(index, item, expander, field)
            expander.add_row(row)
        return expander

    def _build_field(self, index: int, item: dict, expander: Adw.ExpanderRow, field: FieldSpec):
        value = item.get(field.key, field.default)

        if field.kind == "bool":
            row = Adw.SwitchRow(title=t(field.label), subtitle=t(field.subtitle) or None)
            row.set_active(bool(value))

            def on_toggle(widget, _pspec) -> None:
                item[field.key] = bool(widget.get_active())
                self._save()

            row.connect("notify::active", on_toggle)
            return row, None

        if field.kind in ("int", "float"):
            row = Adw.SpinRow.new_with_range(field.minimum, field.maximum, field.step)
            row.set_title(t(field.label))
            if field.subtitle:
                row.set_subtitle(t(field.subtitle))
            row.set_digits(field.digits)
            try:
                row.set_value(float(value))
            except (TypeError, ValueError):
                row.set_value(float(field.default or 0))

            def on_change(widget, _pspec) -> None:
                raw = widget.get_value()
                item[field.key] = int(round(raw)) if field.kind == "int" else float(raw)
                expander.set_title(self._item_title(item))
                self._schedule(f"{index}:{field.key}", self._save)

            row.connect("notify::value", on_change)
            return row, None

        if field.kind == "enum":
            row = Adw.ComboRow(title=t(field.label), subtitle=t(field.subtitle) or None)
            row.set_model(Gtk.StringList.new([t(label) for _value, label in field.choices]))
            values = [choice_value for choice_value, _label in field.choices]
            try:
                row.set_selected(values.index(value))
            except ValueError:
                row.set_selected(0)

            def on_select(widget, _pspec) -> None:
                selected = widget.get_selected()
                if 0 <= selected < len(values):
                    item[field.key] = values[selected]
                    self._save()
                    expander.set_title(self._item_title(item))

            row.connect("notify::selected", on_select)
            return row, None

        # string / command / action
        row = Adw.EntryRow(title=t(field.label))
        if field.subtitle:
            row.set_tooltip_text(t(field.subtitle))
        row.set_show_apply_button(True)
        if field.kind in ("command", "action"):
            row.set_text(_format_command(value))
        else:
            row.set_text("" if value is None else str(value))

        def commit(_widget=None) -> None:
            if field.kind == "command":
                item[field.key] = _parse_command(row.get_text())
            elif field.kind == "action":
                # Preserve the original representation: lists are command
                # arrays, strings are Hyprland dispatchers ("dpms off").
                if isinstance(value, (list, tuple)):
                    item[field.key] = _parse_command(row.get_text())
                else:
                    item[field.key] = row.get_text()
            else:
                item[field.key] = row.get_text()
            self._save()
            expander.set_title(self._item_title(item))

        row.connect("apply", commit)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", lambda _c: commit())
        row.add_controller(focus)
        return row, None

    def _schedule(self, key: str, callback) -> None:
        old = self._timers.pop(key, None)
        if old:
            GLib.source_remove(old)

        def run() -> bool:
            self._timers.pop(key, None)
            callback()
            return False

        self._timers[key] = GLib.timeout_add(300, run)

    def _add(self) -> None:
        if self.new_item:
            item = copy.deepcopy(self.new_item)
        else:
            item = {field.key: copy.deepcopy(field.default) for field in self.fields}
        for field in self.fields:
            item.setdefault(field.key, copy.deepcopy(field.default))
        self.items.append(item)
        self._save()
        self._rebuild()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.items.pop(index)
            self._save()
            self._rebuild()

    def _move(self, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(self.items)):
            return
        target = max(0, min(target, len(self.items) - 1))
        item = self.items.pop(source)
        self.items.insert(target, item)
        self._save()
        self._rebuild()


def add_object_list(
    page,
    backend,
    key,
    defaults,
    fields,
    title,
    description="",
    title_key="name",
    new_item=None,
    allow_reorder=True,
):
    editor = ObjectListEditor(
        page,
        backend,
        key,
        defaults,
        fields,
        title,
        description,
        title_key=title_key,
        new_item=new_item,
        allow_reorder=allow_reorder,
    )
    page.add(editor)
    page.register_search(title, description, key, editor)
    return editor

