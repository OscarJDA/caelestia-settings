"""Pure helpers behind the declarative settings engine.

Nothing in this module imports GTK or runs external commands, so the nested
config maths and the Lua/conf rendering can be unit-tested on their own.

The engine treats every setting as a dotted path into a nested dict:

    appearance.transparency.enabled        -> shell.json
    decoration:blur:enabled                -> Hyprland option

Shell settings are stored as JSON. Hyprland settings are persisted in a Lua
(or .conf) override file that is generated from a JSON sidecar, which keeps
writing idempotent and avoids re-parsing hand-written Lua.
"""

from __future__ import annotations

import json
import re
from typing import Any

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ── Nested dict access ────────────────────────────────────────────────────────


def get_path(data: dict, path: str, default: Any = None) -> Any:
    """Read a dotted path, returning ``default`` when a step is missing."""
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_path(data: dict, path: str, value: Any) -> None:
    """Set a dotted path in-place, creating intermediate dicts as needed."""
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def delete_path(data: dict, path: str) -> bool:
    """Delete a dotted path. Returns True when something was removed."""
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        node = node.get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            return False
    if isinstance(node, dict) and parts[-1] in node:
        del node[parts[-1]]
        return True
    return False


# ── Hyprland option names ────────────────────────────────────────────────────


def hypr_option_to_tree(option: str, value: Any) -> dict:
    """Turn ``general:col.active_border`` into nested config keys.

    Hyprland option names use ``:`` for sections and ``.`` for nested keys
    inside a section (``general:col.active_border`` maps to
    ``general.col.active_border``).

    Hyphenated option names are valid in Hyprland's `.conf` syntax; the Lua
    renderer normalizes them to underscores separately.
    """
    tree: dict = {}
    node = tree
    sections = option.split(":")
    path: list[str] = []
    for section in sections:
        path.extend(section.split("."))
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    return tree


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge ``overlay`` into ``base`` (returns a new dict)."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# ── Lua rendering ────────────────────────────────────────────────────────────

_LUA_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def lua_quote(value: str) -> str:
    """Quote a Python string for Lua.

    Keeps non-ASCII characters as UTF-8 bytes (valid inside Lua strings)
    instead of emitting JSON-style ``\\uXXXX`` escapes, which Lua does not
    understand.
    """
    out = []
    for char in value:
        if char in _LUA_ESCAPES:
            out.append(_LUA_ESCAPES[char])
        elif ord(char) < 0x20:
            out.append(f"\\{ord(char):03d}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def lua_key(key: str) -> str:
    # Hyprland's Lua config API exposes hyphenated options with underscores
    # (``tap-to-click`` -> ``tap_to_click``); shell keys never contain hyphens.
    key = key.replace("-", "_")
    if _IDENT_RE.match(key):
        return key
    return f"[{lua_quote(key)}]"


def lua_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return lua_quote(value)
    if isinstance(value, (list, tuple)):
        return "{ " + ", ".join(lua_value(v) for v in value) + " }"
    if isinstance(value, dict):
        inner = ", ".join(f"{lua_key(k)} = {lua_value(v)}" for k, v in value.items())
        return "{ " + inner + " }"
    raise TypeError(f"Cannot render {type(value).__name__} as Lua")


def _render_lua_table(tree: dict, indent: int) -> list[str]:
    lines: list[str] = []
    pad = "    " * indent
    for key, value in tree.items():
        if isinstance(value, dict):
            if not value:
                continue
            lines.append(f"{pad}{lua_key(key)} = {{")
            lines.extend(_render_lua_table(value, indent + 1))
            lines.append(f"{pad}}},")
        else:
            lines.append(f"{pad}{lua_key(key)} = {lua_value(value)},")
    return lines


def render_lua_config(tree: dict, header: str = "") -> str:
    """Render a nested dict as a single ``hl.config({ ... })`` call."""
    lines: list[str] = []
    if header:
        lines.extend(f"-- {line}" if line else "--" for line in header.splitlines())
    if not tree:
        lines.append("-- No overrides configured.")
        return "\n".join(lines).rstrip() + "\n"
    lines.append("hl.config({")
    lines.extend(_render_lua_table(tree, 1))
    lines.append("})")
    return "\n".join(lines).rstrip() + "\n"


def render_lua_extras(extras: dict) -> str:
    """Render curves, per-leaf animations and gesture bindings as Lua calls."""
    lines: list[str] = []

    curves = extras.get("curves") or {}
    if curves:
        lines.extend(["", "-- Animation curves"])
        for name, curve in curves.items():
            points = curve.get("points") or [[0.0, 0.0], [1.0, 1.0]]
            point_table = ", ".join(f"{{ {float(point[0])}, {float(point[1])} }}" for point in points[:2])
            lines.append(
                f"hl.curve({lua_quote(str(name))}, {{ type = \"bezier\", points = {{ {point_table} }} }})"
            )

    animations = extras.get("animations") or {}
    if animations:
        lines.extend(["", "-- Per-leaf animations"])
        for leaf, anim in animations.items():
            parts = [f"leaf = {lua_quote(str(leaf))}", f"enabled = {lua_value(bool(anim.get('enabled', True)))}"]
            if anim.get("speed") is not None:
                parts.append(f"speed = {float(anim.get('speed', 0))}")
            if anim.get("bezier"):
                parts.append(f"bezier = {lua_quote(str(anim['bezier']))}")
            if anim.get("style"):
                parts.append(f"style = {lua_quote(str(anim['style']))}")
            lines.append(f"hl.animation({{ {', '.join(parts)} }})")

    gestures = extras.get("gestures") or []
    if gestures:
        lines.extend(["", "-- Gesture bindings"])
        for gesture in gestures:
            if not isinstance(gesture, dict):
                continue
            parts = []
            for key in ("fingers", "direction", "action", "workspace_name"):
                value = gesture.get(key)
                if value in (None, ""):
                    continue
                parts.append(f"{key} = {lua_value(value)}")
            if parts:
                lines.append(f"hl.gesture({{ {', '.join(parts)} }})")

    return "\n".join(lines).rstrip() + "\n" if lines else ""



# ── Hyprland .conf rendering ─────────────────────────────────────────────────


def conf_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return value
    raise TypeError(f"Cannot render {type(value).__name__} as a Hyprland value")


def render_conf_overrides(tree: dict, header: str = "") -> str:
    """Render a nested dict as flat ``section:key = value`` lines."""
    lines: list[str] = []
    if header:
        lines.extend(f"# {line}" if line else "#" for line in header.splitlines())

    def walk(node: dict, prefix: list[str]) -> None:
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value, prefix + [key])
            elif isinstance(value, (bool, int, float, str)):
                lines.append(f"{':'.join(prefix + [key])} = {conf_value(value)}")

    walk(tree, [])
    return "\n".join(lines).rstrip() + "\n"


def render_conf_extras(extras: dict) -> str:
    """Curves and animations in classic ``.conf`` syntax.

    Gesture bindings are a Lua-only Hyprland API and are intentionally skipped
    (the UI hides that editor in .conf mode).
    """
    lines: list[str] = []

    curves = extras.get("curves") or {}
    if curves:
        lines.extend(["", "# Animation curves"])
        for name, curve in curves.items():
            points = curve.get("points") or [[0.0, 0.0], [1.0, 1.0]]
            (x0, y0), (x1, y1) = points[0], points[1]
            lines.append(f"bezier = {name}, {float(x0)}, {float(y0)}, {float(x1)}, {float(y1)}")

    animations = extras.get("animations") or {}
    if animations:
        lines.extend(["", "# Per-leaf animations"])
        for leaf, anim in animations.items():
            enabled = 1 if anim.get("enabled", True) else 0
            speed = float(anim.get("speed", 0))
            style = anim.get("style") or ""
            bezier = anim.get("bezier") or ""
            lines.append(f"animation = {leaf}, {enabled}, {speed}, {bezier}, {style}")

    return "\n".join(lines).rstrip() + "\n" if lines else ""



# ── Forgiving reads of hyprctl output ───────────────────────────────────────


def parse_hypr_option(raw: dict, kind: str | None = None) -> Any:
    """Extract the useful value from ``hyprctl -j getoption`` output."""
    if "bool" in raw:
        return bool(raw["bool"])
    if "int" in raw:
        return int(raw["int"])
    if "float" in raw:
        return float(raw["float"])
    if "str" in raw:
        value = raw["str"]
        return "" if value == "[[EMPTY]]" else value
    if "css" in raw:
        text = str(raw["css"]).strip()
        if kind in ("int", "float"):
            first = text.split()[0] if text else "0"
            try:
                return int(float(first)) if kind == "int" else float(first)
            except ValueError:
                return 0
        return text
    if "gradient" in raw:
        return raw["gradient"]
    if "color" in raw:
        return raw["color"]
    if "vec2" in raw:
        value = raw["vec2"]
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return f"{value[0]} {value[1]}"
        return value
    return None


def json_dumps(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
