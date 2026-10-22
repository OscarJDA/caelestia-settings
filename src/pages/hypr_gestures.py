"""Hyprland gesture settings and managed gesture bindings (C5).

The numeric swipe options are regular Hyprland config options.  Additional
gesture bindings are stored in the generated override layer; gestures already
defined in Caelestia's own ``gestures.lua`` are left untouched.
"""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from src.hypr_settings import HyprBackend, is_lua_mode
from src.settings_editors import FieldSpec, add_object_list
from src.settings_engine import SettingsPage, make_backend_error_toast
from src.settings_schema import HYPR_GESTURES_SPEC
from src.lang import t  # noqa: E402

GESTURE_FIELDS = [
    FieldSpec("fingers", "Fingers", kind="int", default=3, minimum=2, maximum=10),
    FieldSpec(
        "direction",
        "Direction",
        kind="enum",
        default="horizontal",
        choices=(
            ("horizontal", "Horizontal"),
            ("vertical", "Vertical"),
            ("left", "Left"),
            ("right", "Right"),
            ("up", "Up"),
            ("down", "Down"),
        ),
    ),
    FieldSpec(
        "action",
        "Action",
        default="workspace",
        subtitle="workspace, scroll_move, special, close, fullscreen, ...",
    ),
    FieldSpec("workspace_name", "Workspace name", default="", subtitle="Used by the special action"),
]

NEW_GESTURE = {
    "fingers": 3,
    "direction": "horizontal",
    "action": "workspace",
    "workspace_name": "",
}


class GestureBackend:
    """Adapter that lets the generic object-list editor manage gestures."""

    def __init__(self, backend: HyprBackend) -> None:
        self.backend = backend

    def available(self, key: str) -> bool:
        return is_lua_mode()

    def get(self, key: str, kind: str | None = None, default=None):
        if key == "gestures":
            return self.backend.get_gestures()
        return default

    def set(self, key: str, value, label: str | None = None, record: bool = True) -> bool:
        if key != "gestures":
            return False
        return self.backend.set_gestures(value, label=label, record=record)


class GesturesPage(SettingsPage):
    def __init__(self, main_window, backend=None):
        backend = backend or HyprBackend(error_sink=make_backend_error_toast(main_window))
        super().__init__(
            main_window,
            HYPR_GESTURES_SPEC,
            backend,
            custom_builders=[self._build_custom],
        )

    def _build_custom(self, page):
        if not is_lua_mode():
            row = Adw.ActionRow(
                title=t("Gesture bindings require the Lua config"),
                subtitle=t("The .conf syntax cannot express hl.gesture() bindings."),
            )
            group = Adw.PreferencesGroup(title=t("Gesture bindings"))
            group.add(row)
            page.add(group)
            return

        add_object_list(
            page,
            GestureBackend(self.backend),
            "gestures",
            [],
            GESTURE_FIELDS,
            "Additional gesture bindings",
            "Gestures managed by Caelestia Settings. Gestures in gestures.lua are left untouched.",
            title_key="action",
            new_item=NEW_GESTURE,
        )
