"""Pure window-rule helpers (no GTK imports).

Lua/conf rendering and the rule tester live here so they can be unit-tested
without a display or PyGObject.
"""

from __future__ import annotations

import re

from src.settings_core import lua_quote, lua_value

MATCH_FIELDS: tuple[tuple[str, str], ...] = (
    ("class", "Class"),
    ("title", "Title"),
    ("initial_title", "Initial title"),
    ("tag", "Tag"),
    ("xwayland", "XWayland (true/false)"),
)

RULE_BOOL_FIELDS: tuple[str, ...] = (
    "float",
    "pin",
    "center",
    "fullscreen",
    "no_blur",
    "no_shadow",
    "no_anim",
    "no_dim",
    "immediate",
    "tile",
    "no_initial_focus",
    "stay_focused",
)

RULE_STRING_FIELDS: tuple[str, ...] = (
    "size",
    "move",
    "workspace",
    "monitor",
    "opacity",
    "group",
    "idle_inhibit",
    "content",
    "suppress_event",
)

# Classic .conf rule names differ from the Lua API for a few boolean/string
# rules (noblur vs no_blur, idleinhibit vs idle_inhibit, ...).
_CONF_NAME_MAP = {
    "no_blur": "noblur",
    "no_shadow": "noshadow",
    "no_anim": "noanim",
    "no_dim": "nodim",
    "no_initial_focus": "noinitialfocus",
    "stay_focused": "stayfocused",
    "idle_inhibit": "idleinhibit",
    "suppress_event": "suppressevent",
}


def _match_pair(rule: dict) -> tuple[str, object]:
    field = str(rule.get("match_field", "class"))
    value = rule.get("match_value", "")
    if field == "xwayland":
        return field, str(value).strip().lower() in ("1", "true", "yes", "on")
    return field, str(value)


def render_lua_rule(rule: dict) -> str | None:
    field, value = _match_pair(rule)
    if field == "xwayland":
        match = f"xwayland = {lua_value(bool(value))}"
    else:
        if not value:
            return None
        match = f"{field} = {lua_quote(str(value))}"

    parts = [f"match = {{ {match} }}"]
    for name in RULE_BOOL_FIELDS:
        if rule.get(name):
            parts.append(f"{name} = true")
    for name in RULE_STRING_FIELDS:
        text = str(rule.get(name, "") or "")
        if text:
            parts.append(f"{name} = {lua_quote(text)}")
    return f"hl.window_rule({{ {', '.join(parts)} }})"


def render_lua_rules(rules: list[dict]) -> list[str]:
    lines = []
    for rule in rules:
        rendered = render_lua_rule(rule)
        if rendered:
            lines.append(rendered)
    return lines


def render_conf_rule(rule: dict) -> list[str]:
    field, value = _match_pair(rule)
    if field == "xwayland":
        match = f"match:xwayland {1 if value else 0}"
    else:
        if not value:
            return []
        match = f"match:{field} {value}"

    lines = []
    for name in RULE_BOOL_FIELDS:
        if rule.get(name):
            lines.append(f"windowrule = {_CONF_NAME_MAP.get(name, name)} true, {match}")
    for name in RULE_STRING_FIELDS:
        text = str(rule.get(name, "") or "")
        if text:
            lines.append(f"windowrule = {_CONF_NAME_MAP.get(name, name)} {text}, {match}")
    return lines


def render_conf_rules(rules: list[dict]) -> list[str]:
    lines = []
    for rule in rules:
        lines.extend(render_conf_rule(rule))
    return lines


def rule_matches_client(rule: dict, client: dict) -> bool:
    field, value = _match_pair(rule)
    if field == "xwayland":
        return bool(client.get("xwayland", False)) == bool(value)
    if field == "tag":
        tags = client.get("tags") or []
        if not isinstance(tags, list):
            return False
        for tag in tags:
            try:
                if re.search(str(value), str(tag)):
                    return True
            except re.error:
                if str(value) == str(tag):
                    return True
        return False
    haystack = str(client.get(field, "") or "")
    try:
        return re.search(str(value), haystack) is not None
    except re.error:
        return str(value).casefold() in haystack.casefold()


def match_rules_against_clients(rules: list[dict], clients: list[dict]) -> list[tuple[dict, list[dict]]]:
    results = []
    for rule in rules:
        matched = [client for client in clients if rule_matches_client(rule, client)]
        results.append((rule, matched))
    return results
