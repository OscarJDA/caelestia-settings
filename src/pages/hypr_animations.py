"""Hyprland animation and curve editor (C3).

Reads the live animation table from ``hyprctl -j animations`` and writes
overrides through :class:`~src.hypr_settings.HyprBackend`, which keeps the
generated override layer in sync.
"""

from __future__ import annotations

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.hypr_settings import HYPR_INCLUDES, HyprBackend
from src.settings_engine import SettingsPage, make_backend_error_toast
from src.settings_schema import HYPR_ANIMATIONS_SPEC
from src.lang import t  # noqa: E402

ANIMATIONS_LUA = HYPR_INCLUDES / "animations.lua"


def _base_curve_names() -> set[str]:
    """Curve names declared by the user's (Caelestia) animations.lua."""
    try:
        if ANIMATIONS_LUA.exists():
            text = ANIMATIONS_LUA.read_text(encoding="utf-8")
            return set(re.findall(r"hl\.curve\s*\(\s*[\"']([^\"']+)[\"']", text))
    except OSError as exc:
        print(f"animations.lua read failed: {exc}")
    return set()

_COMMON = (
    "windowsIn",
    "windowsOut",
    "windowsMove",
    "workspaces",
    "specialWorkspace",
    "fade",
    "fadeDim",
    "border",
    "layersIn",
    "layersOut",
    "fadeLayers",
    "global",
)


def _small_button(icon: str, tooltip: str, callback) -> Gtk.Button:
    button = Gtk.Button(icon_name=icon)
    button.set_valign(Gtk.Align.CENTER)
    button.set_tooltip_text(t(tooltip))
    button.add_css_class("flat")
    button.connect("clicked", callback)
    return button


class CurveEditor(Adw.PreferencesGroup):
    def __init__(self, page, backend: HyprBackend) -> None:
        super().__init__(
            title=t("Animation curves"),
            description=t("Bezier curves used by the animations. Editing a built-in curve creates an override."),
        )
        self.page = page
        self.backend = backend
        self._rows: list[Gtk.Widget] = []
        self._timers: dict[str, int] = {}
        self._rebuild()
        page.add_refresh_callback(self.reload)

    def _data(self) -> dict[str, list[list[float]]]:
        _animations, live_curves = self.backend.get_live_animations()
        managed = self.backend.load_extras()["curves"]
        base = _base_curve_names()
        curves = {}
        for curve in live_curves:
            name = curve.get("name")
            if not name or str(name).startswith("__"):
                continue
            if base and name not in base and name not in managed:
                continue
            curves[name] = [
                [float(curve.get("X0", 0.0)), float(curve.get("Y0", 0.0))],
                [float(curve.get("X1", 1.0)), float(curve.get("Y1", 1.0))],
            ]
        for name, curve in managed.items():
            curves.setdefault(name, curve.get("points") or [[0.0, 0.0], [1.0, 1.0]])
        return curves

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        for timer in list(self._timers.values()):
            GLib.source_remove(timer)
        self._timers.clear()
        self._clear()
        managed = self.backend.load_extras()["curves"]
        for name, points in sorted(self._data().items()):
            expander = self._make_curve(name, points, name in managed)
            self.add(expander)
            self._rows.append(expander)
            self.page.register_search(name, "Animation curve", f"bezier curve {name}", expander)

        add_row = Adw.ActionRow(title=t("Add curve"))
        entry = Gtk.Entry()
        entry.set_placeholder_text(t("Curve name"))
        entry.set_valign(Gtk.Align.CENTER)
        add_button = _small_button("list-add-symbolic", t("Add curve"), lambda _b: self._add(entry.get_text()))
        entry.connect("activate", lambda _e: self._add(entry.get_text()))
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        box.set_valign(Gtk.Align.CENTER)
        box.append(entry)
        box.append(add_button)
        add_row.add_suffix(box)
        self.add(add_row)
        self._rows.append(add_row)

    def _make_curve(self, name: str, points, managed: bool) -> Adw.ExpanderRow:
        expander = Adw.ExpanderRow(title=name, subtitle=t("Bezier curve"))
        state = {
            "x0": float(points[0][0]),
            "y0": float(points[0][1]),
            "x1": float(points[1][0]),
            "y1": float(points[1][1]),
        }

        def schedule() -> None:
            timer = self._timers.pop(name, None)
            if timer:
                GLib.source_remove(timer)

            def commit() -> bool:
                self._timers.pop(name, None)
                self.backend.set_curve(name, [[state["x0"], state["y0"]], [state["x1"], state["y1"]]])
                return False

            self._timers[name] = GLib.timeout_add(350, commit)

        for key, label in (("x0", "P1 X"), ("y0", "P1 Y"), ("x1", "P2 X"), ("y1", "P2 Y")):
            row = Adw.SpinRow.new_with_range(-2.0, 3.0, 0.01)
            row.set_title(label)
            row.set_digits(2)
            row.set_value(state[key])
            row.connect("notify::value", lambda widget, _pspec, k=key: (state.__setitem__(k, widget.get_value()), schedule()))
            expander.add_row(row)

        if managed:
            expander.add_suffix(_small_button("edit-undo-symbolic", "Reset to the built-in curve", lambda _b: self._reset(name)))
        return expander

    def _reset(self, name: str) -> None:
        self.backend.remove_curve(name)
        self._rebuild()

    def _add(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        self.backend.set_curve(name, [[0.0, 0.0], [1.0, 1.0]])
        self._rebuild()

    def reload(self) -> None:
        self._rebuild()


class AnimationEditor(Adw.PreferencesGroup):
    def __init__(self, page, backend: HyprBackend) -> None:
        super().__init__(
            title=t("Animations"),
            description=t("Per-leaf speed, curve and style. Disable a leaf to remove its animation."),
        )
        self.page = page
        self.backend = backend
        self._rows: list[Gtk.Widget] = []
        self._timers: dict[str, int] = {}
        self._rebuild()
        page.add_refresh_callback(self.reload)

    def _data(self) -> list[dict]:
        animations, _curves = self.backend.get_live_animations()
        return [anim for anim in animations if not str(anim.get("name", "")).startswith("__internal")]

    def _curve_names(self) -> list[str]:
        managed = self.backend.load_extras()["curves"]
        base = _base_curve_names()
        names = [curve.get("name", "") for curve in self.backend.get_live_animations()[1]]
        names = [
            name
            for name in names
            if name
            and not str(name).startswith("__")
            and (not base or name in base or name in managed)
        ]
        return [""] + sorted(set(names))

    def _clear(self) -> None:
        for row in self._rows:
            self.remove(row)
        self._rows = []

    def _rebuild(self) -> None:
        for timer in list(self._timers.values()):
            GLib.source_remove(timer)
        self._timers.clear()
        self._clear()
        data = {anim.get("name"): anim for anim in self._data()}
        order = [name for name in _COMMON if name in data]
        order += sorted(name for name in data if name not in order)
        curves = self._curve_names()
        for name in order:
            expander = self._make_animation(name, data[name], curves)
            self.add(expander)
            self._rows.append(expander)
            self.page.register_search(name, "Hyprland animation", f"animation {name}", expander)

    def _make_animation(self, leaf: str, anim: dict, curves: list[str]) -> Adw.ExpanderRow:
        speed = float(anim.get("speed", 0.0))
        bezier = str(anim.get("bezier", "") or "")
        style = str(anim.get("style", "") or "")
        expander = Adw.ExpanderRow(
            title=leaf,
            subtitle=f"{bezier or 'default'} · {speed:g}",
        )
        state = {
            "enabled": bool(anim.get("enabled", True)),
            "speed": speed,
            "bezier": bezier,
            "style": style,
        }

        def schedule() -> None:
            timer = self._timers.pop(leaf, None)
            if timer:
                GLib.source_remove(timer)

            def commit() -> bool:
                self._timers.pop(leaf, None)
                self.backend.set_animation(
                    leaf,
                    state["enabled"],
                    state["speed"],
                    state["bezier"],
                    state["style"],
                )
                expander.set_subtitle(f"{state['bezier'] or 'default'} · {state['speed']:g}")
                return False

            self._timers[leaf] = GLib.timeout_add(300, commit)

        enabled_row = Adw.SwitchRow(title=t("Enabled"))
        enabled_row.set_active(state["enabled"])
        enabled_row.connect("notify::active", lambda row, _p: (state.__setitem__("enabled", row.get_active()), schedule()))
        expander.add_row(enabled_row)

        speed_row = Adw.SpinRow.new_with_range(0.0, 30.0, 0.1)
        speed_row.set_title(t("Speed"))
        speed_row.set_digits(1)
        speed_row.set_value(state["speed"])
        speed_row.connect("notify::value", lambda row, _p: (state.__setitem__("speed", row.get_value()), schedule()))
        expander.add_row(speed_row)

        bezier_row = Adw.ComboRow(title=t("Curve"))
        bezier_row.set_model(Gtk.StringList.new([t("Default") if name == "" else name for name in curves]))
        try:
            bezier_row.set_selected(curves.index(state["bezier"]))
        except ValueError:
            bezier_row.set_selected(0)
        bezier_row.connect(
            "notify::selected",
            lambda row, _p: (state.__setitem__("bezier", curves[row.get_selected()] if 0 <= row.get_selected() < len(curves) else ""), schedule()),
        )
        expander.add_row(bezier_row)

        style_row = Adw.EntryRow(title=t("Style"))
        style_row.set_show_apply_button(True)
        style_row.set_text(state["style"])
        style_row.set_tooltip_text(t("Examples: slide, popin, fade, slidefadevert 15%"))

        def commit_style(_widget=None) -> None:
            state["style"] = style_row.get_text()
            schedule()

        style_row.connect("apply", commit_style)
        focus = Gtk.EventControllerFocus.new()
        focus.connect("leave", lambda _c: commit_style())
        style_row.add_controller(focus)
        expander.add_row(style_row)

        if leaf in self.backend.load_extras()["animations"]:
            expander.add_suffix(
                _small_button("edit-undo-symbolic", t("Reset this animation"), lambda _b: self._reset(leaf))
            )
        return expander

    def _reset(self, leaf: str) -> None:
        self.backend.remove_animation(leaf)
        self._rebuild()

    def reload(self) -> None:
        self._rebuild()


class AnimationsPage(SettingsPage):
    def __init__(self, main_window, backend=None):
        backend = backend or HyprBackend(error_sink=make_backend_error_toast(main_window))
        super().__init__(
            main_window,
            HYPR_ANIMATIONS_SPEC,
            backend,
            custom_builders=[self._build_custom],
        )

    def _build_custom(self, page):
        page.add(CurveEditor(page, self.backend))
        page.add(AnimationEditor(page, self.backend))
