"""Advanced Hyprland window rules (C11).

This module owns the data model and editor used by the "Advanced" tab on the
Window Rules page. Pure rendering/matching helpers live in
:mod:`src.rules_core` so they can be tested without GTK.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.rules_core import (
    MATCH_FIELDS,
    RULE_BOOL_FIELDS,
    RULE_STRING_FIELDS,
    match_rules_against_clients,
)
from src.safe_io import atomic_write_json, read_json
from src.settings_editors import FieldSpec, add_object_list
from src.settings_engine import JsonFileBackend, SettingsPage
from src.settings_schema import PageSpec
from src.lang import t  # noqa: E402

ADVANCED_RULES_JSON = Path.home() / ".config" / "caelestia-settings" / "advanced_rules.json"

RULE_FIELDS = (
    [
        FieldSpec("match_field", "Match field", kind="enum", default="class", choices=MATCH_FIELDS),
        FieldSpec("match_value", "Match value", default="", subtitle="Regex for class/title; true/false for XWayland"),
    ]
    + [
        FieldSpec(name, name.replace("_", " ").title(), kind="bool", default=False)
        for name in RULE_BOOL_FIELDS
    ]
    + [
        FieldSpec(name, name.replace("_", " ").title(), default="")
        for name in RULE_STRING_FIELDS
    ]
)

NEW_RULE = {
    "match_field": "class",
    "match_value": "",
    **{name: False for name in RULE_BOOL_FIELDS},
    **{name: "" for name in RULE_STRING_FIELDS},
}


def empty_rules_document() -> dict:
    return {"rules": []}


def load_advanced_rules() -> list[dict]:
    data = read_json(ADVANCED_RULES_JSON, empty_rules_document())
    rules = data.get("rules")
    return rules if isinstance(rules, list) else []


def save_advanced_rules(rules: list[dict]) -> None:
    atomic_write_json(ADVANCED_RULES_JSON, {"rules": rules})


class AdvancedRulesPage(SettingsPage):
    """A preferences page used as the third tab of the Window Rules page."""

    def __init__(self, on_apply, main_window=None):
        self.on_apply = on_apply
        self.main_window = main_window
        backend = JsonFileBackend(ADVANCED_RULES_JSON, empty_rules_document())
        spec = PageSpec(page_id="advanced-rules", title="Advanced rules")
        super().__init__(main_window, spec, backend, custom_builders=[self._build_custom])

    def _build_custom(self, page):
        self.editor = add_object_list(
            page,
            self.backend,
            "rules",
            [],
            RULE_FIELDS,
            "Custom window rules",
            "Match a window and apply Hyprland rules. False switches are omitted.",
            title_key="match_value",
            new_item=copy.deepcopy(NEW_RULE),
        )

        group = Adw.PreferencesGroup(title=t("Apply"))
        apply_row = Adw.ActionRow(
            title=t("Save and apply"),
            subtitle=t("Regenerates the rules file and reloads Hyprland"),
        )
        button = Gtk.Button(label=t("Save & Apply"))
        button.add_css_class("suggested-action")
        button.set_valign(Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: self.on_apply())
        apply_row.add_suffix(button)
        group.add(apply_row)
        page.add(group)

        test_group = Adw.PreferencesGroup(title=t("Rule tester"))
        test_row = Adw.ActionRow(
            title=t("Test against open windows"),
            subtitle=t("Shows which currently open windows match each rule"),
        )
        test_button = Gtk.Button(label=t("Test"))
        test_button.set_valign(Gtk.Align.CENTER)
        test_button.connect("clicked", lambda _b: self._test_rules())
        test_row.add_suffix(test_button)
        test_group.add(test_row)
        page.add(test_group)

    def _test_rules(self) -> None:
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            clients = json.loads(result.stdout) if result.returncode == 0 else []
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            clients = []

        dialog = Adw.AlertDialog(heading=t("Rule test"))
        if not clients:
            dialog.set_body(t("No open windows were reported by Hyprland."))
            dialog.add_response("close", t("Close"))
            dialog.present(self.get_root())
            return

        results = match_rules_against_clients(self.rules(), clients)
        lines = []
        for rule, matched in results:
            field = str(rule.get("match_field", "class"))
            value = str(rule.get("match_value", ""))
            if not value:
                continue
            if matched:
                titles = " | ".join(
                    str(client.get("title") or client.get("class") or "?")[:80] for client in matched
                )
                lines.append(
                    f"<b>{GLib.markup_escape_text(f'{field}: {value}')}</b> — "
                    f"{len(matched)} window(s): {GLib.markup_escape_text(titles)}"
                )
            else:
                lines.append(
                    f"<span alpha='60%'>{GLib.markup_escape_text(f'{field}: {value}')} — no matches</span>"
                )

        label = Gtk.Label()
        label.set_markup("\n\n".join(lines) if lines else "No rules defined yet.")
        label.set_wrap(True)
        label.set_xalign(0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_size_request(560, 320)
        scroller.set_child(label)
        dialog.set_extra_child(scroller)
        dialog.add_response("close", t("Close"))
        dialog.present(self.get_root())

    def rules(self) -> list[dict]:
        return self.editor.get_items() if hasattr(self, "editor") else []
