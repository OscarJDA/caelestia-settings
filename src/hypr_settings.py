"""Hyprland settings backend.

Values are read from the running compositor with ``hyprctl getoption`` and
persisted in a generated override layer:

* Lua config (Caelestia 2.5+): ``~/.config/caelestia/settings-overrides.lua``
  is required from ``hypr-user.lua`` and applied live through ``hyprctl eval``.
* Classic config: ``~/.config/hypr/hyprland/settings-overrides.conf`` is
  sourced from ``hyprland.conf`` and applied live through ``hyprctl keyword``.

A JSON sidecar keeps the authoritative list of overrides, so the generated
files can always be rebuilt and never need to be parsed back.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

from src.safe_io import HISTORY, atomic_write_json, atomic_write_text, read_json
from src.settings_core import (
    conf_value,
    hypr_option_to_tree,
    lua_value,
    parse_hypr_option,
    render_conf_extras,
    render_conf_overrides,
    render_lua_config,
    render_lua_extras,
)

HOME = Path(os.path.expanduser("~"))
APP_CONFIG_DIR = HOME / ".config" / "caelestia-settings"
OVERRIDES_JSON = APP_CONFIG_DIR / "hypr_overrides.json"
EXTRAS_JSON = APP_CONFIG_DIR / "hypr_extras.json"

HYPR_DIR = HOME / ".config" / "hypr"
HYPR_CONF = HYPR_DIR / "hyprland.conf"
HYPR_LUA = HYPR_DIR / "hyprland.lua"
HYPR_INCLUDES = HYPR_DIR / "hyprland"
CAELESTIA_DIR = HOME / ".config" / "caelestia"
CAELESTIA_HYPR_USER = CAELESTIA_DIR / "hypr-user.lua"
LUA_OVERRIDES = CAELESTIA_DIR / "settings-overrides.lua"
CONF_OVERRIDES = HYPR_INCLUDES / "settings-overrides.conf"

LUA_HEADER = (
    "Managed by Caelestia Settings — changes made here are regenerated.\n"
    "Override layer loaded after the Caelestia defaults."
)


def _run(args: list[str], timeout: int = 3) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Hyprland command failed ({' '.join(args)}): {exc}")
        return None


def is_lua_mode() -> bool:
    """Mirror of ``src.config.is_lua_mode`` without importing caelestia_core."""
    return HYPR_LUA.exists() or (CAELESTIA_HYPR_USER.exists() and not HYPR_CONF.exists())


# Empty strings are meaningful for these options ("no variant"/"no options").
# For most Hyprland strings, empty means "remove the override / use default".
_EMPTY_IS_VALUE = {"input:kb_variant", "input:kb_options"}


class HyprBackend:
    """Read live options from Hyprland and persist overrides safely."""

    def __init__(self, error_sink=None) -> None:
        self.error_sink = error_sink
        self._available: dict[str, bool] = {}
        self._raw_cache: dict[str, dict | None] = {}

    # ── Reading ───────────────────────────────────────────────────────────

    def get_raw(self, option: str) -> dict | None:
        if option in self._raw_cache:
            return self._raw_cache[option]
        result = _run(["hyprctl", "-j", "getoption", option])
        if result is None or result.returncode != 0:
            self._raw_cache[option] = None
            return None
        text = result.stdout.strip()
        if not text or text.startswith("no such option"):
            self._raw_cache[option] = None
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self._raw_cache[option] = None
            return None
        if not isinstance(data, dict) or "option" not in data:
            self._raw_cache[option] = None
            return None
        self._raw_cache[option] = data
        return data

    def invalidate(self, option: str | None = None) -> None:
        if option is None:
            self._raw_cache.clear()
            self._available.clear()
        else:
            self._raw_cache.pop(option, None)
            self._available.pop(option, None)

    def available(self, option: str) -> bool:
        if option not in self._available:
            self._available[option] = self.get_raw(option) is not None
        return self._available[option]

    def get(self, option: str, kind: str | None = None, default=None):
        raw = self.get_raw(option)
        if raw is None:
            return default
        value = parse_hypr_option(raw, kind)
        return default if value is None else value

    # ── Override storage ──────────────────────────────────────────────────

    def load_overrides(self) -> dict:
        return read_json(OVERRIDES_JSON, {})

    def _persist(self, tree: dict) -> bool:
        atomic_write_json(OVERRIDES_JSON, tree)
        extras = self.load_extras()
        if is_lua_mode():
            self._ensure_lua_require()
            extras_text = render_lua_extras(extras)
            config_text = render_lua_config(tree, LUA_HEADER)
            if not tree and extras_text:
                config_text = "\n".join(f"-- {line}" for line in LUA_HEADER.splitlines()) + "\n"
            atomic_write_text(LUA_OVERRIDES, config_text + extras_text)
        else:
            self._ensure_conf_source()
            extras_text = render_conf_extras(extras)
            config_text = render_conf_overrides(tree, LUA_HEADER)
            if not tree and extras_text:
                config_text = "\n".join(f"# {line}" for line in LUA_HEADER.splitlines()) + "\n"
            atomic_write_text(CONF_OVERRIDES, config_text + extras_text)
        return True

    # ── Curves, animations and gestures ───────────────────────────────────

    def load_extras(self) -> dict:
        data = read_json(EXTRAS_JSON, {})
        return {
            "curves": data.get("curves") if isinstance(data.get("curves"), dict) else {},
            "animations": data.get("animations") if isinstance(data.get("animations"), dict) else {},
            "gestures": data.get("gestures") if isinstance(data.get("gestures"), list) else [],
        }

    def _write_extras(self, extras: dict) -> bool:
        atomic_write_json(EXTRAS_JSON, extras)
        self._persist(self.load_overrides())
        return True

    def _eval(self, code: str) -> tuple[bool, str]:
        result = _run(["hyprctl", "eval", code])
        if result is None:
            return False, "hyprctl not available"
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0 and "error" not in output.lower(), output

    def get_live_animations(self) -> tuple[list[dict], list[dict]]:
        result = _run(["hyprctl", "-j", "animations"])
        if result is None or result.returncode != 0:
            return [], []
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return [], []
        if not isinstance(data, list) or len(data) < 2:
            return [], []
        animations = data[0] if isinstance(data[0], list) else []
        curves = data[1] if isinstance(data[1], list) else []
        return animations, curves

    def set_curve(self, name: str, points, label: str | None = None, record: bool = True) -> bool:
        name = str(name).strip()
        if not name:
            return False
        points = [[float(points[0][0]), float(points[0][1])], [float(points[1][0]), float(points[1][1])]]
        extras = self.load_extras()
        old = copy.deepcopy(extras["curves"].get(name))
        new = {"type": "bezier", "points": points}
        if old == new:
            return True
        extras["curves"][name] = new
        self._write_extras(extras)
        self._apply_curve(name, new)
        if record:
            HISTORY.push(
                label or f"Curve {name}",
                lambda: self.set_curve(name, old["points"], record=False) if old else self.remove_curve(name, record=False),
                lambda: self.set_curve(name, points, record=False),
            )
        return True

    def remove_curve(self, name: str, label: str | None = None, record: bool = True) -> bool:
        extras = self.load_extras()
        old = copy.deepcopy(extras["curves"].get(name))
        if old is None:
            return True
        del extras["curves"][name]
        self._write_extras(extras)
        _run(["hyprctl", "reload"])
        if record:
            HISTORY.push(
                label or f"Reset curve {name}",
                lambda: self.set_curve(name, old["points"], record=False),
                lambda: self.remove_curve(name, record=False),
            )
        return True

    def _apply_curve(self, name: str, curve: dict) -> tuple[bool, str]:
        points = curve.get("points") or [[0.0, 0.0], [1.0, 1.0]]
        if is_lua_mode():
            (x0, y0), (x1, y1) = points[0], points[1]
            return self._eval(
                "hl.curve("
                f"{lua_value(str(name))}, {{ type = \"bezier\", points = {{ {{ {float(x0)}, {float(y0)} }}, "
                f"{{ {float(x1)}, {float(y1)} }} }} }})"
            )
        (x0, y0), (x1, y1) = points[0], points[1]
        result = _run(["hyprctl", "keyword", "bezier", f"{name}, {float(x0)}, {float(y0)}, {float(x1)}, {float(y1)}"])
        return (result is not None and result.returncode == 0), ""

    def set_animation(
        self,
        leaf: str,
        enabled: bool,
        speed: float,
        bezier: str,
        style: str,
        label: str | None = None,
        record: bool = True,
    ) -> bool:
        extras = self.load_extras()
        old = copy.deepcopy(extras["animations"].get(leaf))
        new = {
            "enabled": bool(enabled),
            "speed": float(speed),
            "bezier": str(bezier or ""),
            "style": str(style or ""),
        }
        if old == new:
            return True
        extras["animations"][leaf] = new
        self._write_extras(extras)
        self._apply_animation(leaf, new)
        if record:
            HISTORY.push(
                label or f"Animation {leaf}",
                lambda: (
                    self.set_animation(leaf, old["enabled"], old["speed"], old["bezier"], old["style"], record=False)
                    if old
                    else self.remove_animation(leaf, record=False)
                ),
                lambda: self.set_animation(leaf, enabled, speed, bezier, style, record=False),
            )
        return True

    def remove_animation(self, leaf: str, label: str | None = None, record: bool = True) -> bool:
        extras = self.load_extras()
        old = copy.deepcopy(extras["animations"].get(leaf))
        if old is None:
            return True
        del extras["animations"][leaf]
        self._write_extras(extras)
        _run(["hyprctl", "reload"])
        if record:
            HISTORY.push(
                label or f"Reset animation {leaf}",
                lambda: self.set_animation(
                    leaf, old["enabled"], old["speed"], old["bezier"], old["style"], record=False
                ),
                lambda: self.remove_animation(leaf, record=False),
            )
        return True

    def _apply_animation(self, leaf: str, anim: dict) -> tuple[bool, str]:
        if is_lua_mode():
            parts = [
                f"leaf = {lua_value(leaf)}",
                f"enabled = {lua_value(bool(anim.get('enabled', True)))}",
                f"speed = {float(anim.get('speed', 0))}",
            ]
            if anim.get("bezier"):
                parts.append(f"bezier = {lua_value(str(anim['bezier']))}")
            if anim.get("style"):
                parts.append(f"style = {lua_value(str(anim['style']))}")
            return self._eval(f"hl.animation({{ {', '.join(parts)} }})")
        result = _run(
            [
                "hyprctl",
                "keyword",
                "animation",
                f"{leaf}, {1 if anim.get('enabled', True) else 0}, {float(anim.get('speed', 0))}, "
                f"{anim.get('bezier') or ''}, {anim.get('style') or ''}",
            ]
        )
        return (result is not None and result.returncode == 0), ""

    def get_gestures(self) -> list[dict]:
        return self.load_extras()["gestures"]

    def set_gestures(self, gestures: list[dict], label: str | None = None, record: bool = True) -> bool:
        extras = self.load_extras()
        old = copy.deepcopy(extras["gestures"])
        new = copy.deepcopy(gestures)
        if old == new:
            return True
        extras["gestures"] = new
        self._write_extras(extras)
        _run(["hyprctl", "reload"])
        if record:
            HISTORY.push(
                label or "Gesture bindings",
                lambda: self.set_gestures(old, record=False),
                lambda: self.set_gestures(new, record=False),
            )
        return True


    def _ensure_lua_require(self) -> None:
        try:
            if not CAELESTIA_HYPR_USER.exists():
                from src import config as app_config

                app_config.ensure_hypr_user_lua()
            text = CAELESTIA_HYPR_USER.read_text(encoding="utf-8")
            if "settings-overrides" not in text:
                addition = (
                    "\n-- Caelestia Settings: Hyprland overrides\n"
                    'pcall(require, "settings-overrides")\n'
                )
                atomic_write_text(CAELESTIA_HYPR_USER, text.rstrip() + addition)
        except OSError as exc:
            print(f"hypr-user.lua konnte nicht erweitert werden: {exc}")

    def _ensure_conf_source(self) -> None:
        try:
            if not HYPR_CONF.exists():
                return
            text = HYPR_CONF.read_text(encoding="utf-8")
            if "settings-overrides.conf" in text:
                return
            addition = "\n# Caelestia Settings overrides\nsource = ~/.config/hypr/hyprland/settings-overrides.conf\n"
            atomic_write_text(HYPR_CONF, text.rstrip() + addition)
        except OSError as exc:
            print(f"hyprland.conf konnte nicht erweitert werden: {exc}")

    def ensure_loaded(self) -> None:
        """Make sure an existing override layer is actually sourced."""
        if not (OVERRIDES_JSON.exists() or EXTRAS_JSON.exists() or LUA_OVERRIDES.exists() or CONF_OVERRIDES.exists()):
            return
        if is_lua_mode():
            self._ensure_lua_require()
        else:
            self._ensure_conf_source()

    @staticmethod
    def _set_in_tree(tree: dict, option: str, value, empty_is_value: bool = False) -> dict:
        """Return a copy of ``tree`` with ``option`` set (or removed if empty)."""
        updated = copy.deepcopy(tree)
        parts: list[str] = []
        for section in option.split(":"):
            parts.extend(section.split("."))

        if value == "" and not empty_is_value:
            node = updated
            for key in parts[:-1]:
                node = node.get(key) if isinstance(node, dict) else None
                if not isinstance(node, dict):
                    return updated
            if isinstance(node, dict):
                node.pop(parts[-1], None)
            return _prune_empty(updated, parts)

        merged = updated
        for key in parts[:-1]:
            child = merged.get(key)
            if not isinstance(child, dict):
                child = {}
                merged[key] = child
            merged = child
        merged[parts[-1]] = value
        return updated

    # ── Live apply ────────────────────────────────────────────────────────

    def _apply_live(self, option: str, value) -> tuple[bool, str]:
        if is_lua_mode():
            code = f"hl.config({lua_value(hypr_option_to_tree(option, value))})"
            result = _run(["hyprctl", "eval", code])
            if result is None:
                return False, "hyprctl not available"
            output = (result.stdout + result.stderr).strip()
            ok = result.returncode == 0 and "error" not in output.lower()
            return ok, output
        result = _run(["hyprctl", "keyword", option, conf_value(value)])
        if result is None:
            return False, "hyprctl not available"
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output

    # ── Writing ───────────────────────────────────────────────────────────

    def set(self, option: str, value, label: str | None = None, record: bool = True) -> bool:
        if not self.available(option):
            self._error(f"{option}: option not supported by this Hyprland version")
            return False

        raw = self.get_raw(option) or {}
        if "int" in raw and isinstance(value, float):
            value = int(round(value))

        hint = None
        if "int" in raw:
            hint = "int"
        elif "float" in raw:
            hint = "float"
        elif "css" in raw:
            hint = "float" if isinstance(value, float) else "int"
        old = self.get(option, kind=hint)
        if old == value:
            return True

        before = self.load_overrides()
        after = self._set_in_tree(
            before, option, value, empty_is_value=option in _EMPTY_IS_VALUE
        )
        self._persist(after)

        ok, output = self._apply_live(option, value)
        if not ok:
            self._persist(before)
            if old is not None:
                self._apply_live(option, old)
            self._error(f"{option}: {output or 'invalid value'}")
            return False

        self.invalidate(option)
        if record and old is not None:
            HISTORY.push(
                label or f"{option} = {value}",
                lambda: self.set(option, old, record=False),
                lambda: self.set(option, value, record=False),
            )
        return True

    def reset(self, option: str, label: str | None = None, record: bool = True) -> bool:
        """Remove an override (the next reload falls back to the base config)."""
        before = self.load_overrides()
        after = self._set_in_tree(before, option, "")
        if before == after:
            return True
        self._persist(after)
        self.invalidate(option)
        if record:
            HISTORY.push(
                label or f"Reset {option}",
                lambda: self._persist(before),
                lambda: self._persist(after),
            )
        return True

    def _error(self, message: str) -> None:
        print(f"Hyprland settings: {message}")
        if self.error_sink:
            self.error_sink(message)


def _prune_empty(tree: dict, path: list[str]) -> dict:
    """Remove empty parent dicts left behind by deleting a nested option."""
    stack: list[tuple[dict, str]] = []
    node = tree
    for key in path[:-1]:
        child = node.get(key) if isinstance(node, dict) else None
        if not isinstance(child, dict):
            return tree
        stack.append((node, key))
        node = child
    while stack:
        parent, key = stack.pop()
        if isinstance(parent.get(key), dict) and not parent[key]:
            del parent[key]
        else:
            break
    return tree
