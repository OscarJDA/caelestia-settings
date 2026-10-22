import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from src.lang import t
from gi.repository import Adw, Gdk, Gtk

import caelestia_core
from src.config import (
    is_lua_mode,
    CAELESTIA_HYPR_USER,
    CAELESTIA_KEYBINDS_LUA,
    HYPR_KEYBINDS_LUA,
    ensure_hypr_user_lua,
    hyprctl_reload,
)
from src.safe_io import atomic_write_text

KEYBINDS_CONF = Path.home() / ".config/hypr/hyprland/keybinds.conf"
VARIABLES_CONF = Path.home() / ".config/hypr/variables.conf"


def get_keybinds_path() -> Path:
    return CAELESTIA_KEYBINDS_LUA if is_lua_mode() else KEYBINDS_CONF

# ── Regex (aus hyprkeys übernommen) ──────────────────────────────────────────

BIND_RE = re.compile(
    r'^(\s*)(bind[a-z]*)\s*=\s*'
    r'([^,]*),\s*'
    r'([^,]*),\s*'
    r'([^,\n#]*?)'
    r'(?:,\s*([^\n#]*?))?'
    r'\s*(?:#\s*(.*))?$',
    re.IGNORECASE,
)
BIND_TYPE_LABELS = {
    "bind":   "Normal",
    "binde":  t("Repeat"),
    "bindl":  t("Lock-Screen"),
    "bindle": t("Lock+Repeat"),
    "bindr":  t("Release"),
    "bindm":  t("Mouse"),
    "bindi":  t("Ignore Inhibit"),
    "bindin": t("Ignore+NonConsume"),
}

DISPATCHERS = sorted([
    "exec", "killactive", "closewindow", "workspace", "movetoworkspace",
    "movetoworkspacesilent", "togglefloating", "fullscreen", "fakefullscreen",
    "dpms", "pin", "movefocus", "movewindow", "resizewindow", "resizeactive",
    "cyclenext", "swapnext", "focuswindow", "focusmonitor", "splitratio",
    "toggleopaque", "movecursortocorner", "workspaceopt", "exit",
    "forcerendererreload", "movecurrentworkspacetomonitor",
    "focusworkspaceoncurrentmonitor", "togglespecialworkspace",
    "swapactiveworkspaces", "bringactivetotop", "alterzorder", "togglesplit",
    "layoutmsg", "global", "submap", "moveoutofgroup", "changegroupactive",
    "togglegroup", "lockactivegroup", "centerwindow",
])


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_variables(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return caelestia_core.parse_variables(path.read_text())
    except Exception as e:
        print(f"Variablen-Parser fehler: {e}")
        return {}


def _resolve(raw: str, variables: dict) -> str:
    return caelestia_core.resolve(raw, variables)


# ── Lua-Bind-Beschreibungen ───────────────────────────────────────────────────
#
# In Lua mode hyprctl reports every shortcut with the generic dispatcher
# "__lua <index>", which says nothing about what the key does — the real action
# only exists inside the Lua config. So we evaluate the config files with a stub
# `hl` table (see _LUA_DUMP_SCRIPT), which records every hl.bind() call as
# "key combination → action", and then match that against the live binds from
# hyprctl by key combination.
LUA_BIND_FILES = [
    HYPR_KEYBINDS_LUA,       # Caelestia's own binds
    CAELESTIA_KEYBINDS_LUA,  # binds added/edited with this app
    CAELESTIA_HYPR_USER,     # anything the user put in hypr-user.lua
]

# Runs with `lua <script> <config files...>`. The stub hl table must swallow
# every call so that loading the config has no side effects: dispatchers are
# only remembered, never executed.
# Output: one line per bind, tab separated:
#   key <TAB> kind <TAB> path <TAB> arg <TAB> variable-name
_LUA_DUMP_SCRIPT = r'''
local home = os.getenv("HOME") or ""

package.path = table.concat({
    home .. "/.config/hypr/?.lua",
    home .. "/.config/hypr/?/init.lua",
    home .. "/.config/hypr/?/?.lua",
    package.path,
}, ";")

local out = {}

local function esc(s)
    s = tostring(s or "")
    return (s:gsub("\\", "\\\\"):gsub("\t", "\\t"):gsub("\n", "\\n"):gsub("\r", "\\r"))
end

local function ser(v)
    if v == nil then return "" end
    local tv = type(v)
    if tv == "string" or tv == "number" or tv == "boolean" then
        return tostring(v)
    end
    if tv == "table" then
        local parts = {}
        for k, val in pairs(v) do
            parts[#parts + 1] = k .. "=" .. ser(val)
        end
        table.sort(parts)
        return "{" .. table.concat(parts, ",") .. "}"
    end
    return tv
end

-- hl.dsp.any.thing(...) builds a nested proxy; calling it returns a marker.
local function proxy(path)
    return setmetatable({}, {
        __index = function(_, k) return proxy(path .. "." .. k) end,
        __call = function(_, a) return { __dsp = path, __arg = ser(a) } end,
    })
end

-- Remember which variables.lua entry was read, so an anonymous function can
-- still be labelled with the variable it was bound to.
local reads = {}
local real_vars = {}
pcall(function() real_vars = require("variables") end)
package.loaded["variables"] = setmetatable({}, {
    __index = function(_, k)
        local v = real_vars[k]
        reads[#reads + 1] = { name = k, value = v }
        return v
    end,
})

-- Stub for utils.functions: remember the call instead of running it.
package.loaded["utils.functions"] = setmetatable({}, {
    __index = function(_, k)
        return function(...)
            local parts = {}
            for i = 1, select("#", ...) do
                parts[i] = ser((select(i, ...)))
            end
            return { __fn = k, __arg = table.concat(parts, ",") }
        end
    end,
})

local function var_name_for(key)
    for i = #reads, 1, -1 do
        local v = reads[i].value
        local tv = type(v)
        if tv == "string" and v == key then return reads[i].name end
        if tv == "table" then
            for _, x in ipairs(v) do
                if x == key then return reads[i].name end
            end
        end
    end
    return ""
end

local hl = setmetatable({
    dsp = proxy("dsp"),
    bind = function(key, action, _)
        local kind, path, arg = "other", type(action), ""
        if type(action) == "table" and action.__dsp then
            kind, path, arg = "dsp", action.__dsp, action.__arg
        elseif type(action) == "table" and action.__fn then
            kind, path, arg = "fn", action.__fn, action.__arg
        elseif type(action) == "function" then
            kind = "anon"
            pcall(function()
                local info = debug.getinfo(action, "S")
                path = tostring(info.short_src) .. ":" .. tostring(info.linedefined)
            end)
        end
        out[#out + 1] = table.concat(
            { esc(key), kind, esc(path), esc(arg), esc(var_name_for(key)) }, "\t"
        )
    end,
}, {
    __index = function(_, k) return proxy(k) end,
})

_G.hl = hl

for i = 1, #arg do
    pcall(dofile, arg[i])
end

io.write(table.concat(out, "\n"), "\n")
'''

# hl.dsp.* path → what it does
ACTION_LABELS = {
    "dsp.window.close":              t("Close active window"),
    "dsp.window.float":              t("Toggle floating"),
    "dsp.window.fullscreen":         t("Toggle fullscreen"),
    "dsp.window.pin":                t("Pin window"),
    "dsp.window.center":             t("Center window"),
    "dsp.window.drag":               t("Move window (drag)"),
    "dsp.window.resize":             t("Resize window"),
    "dsp.window.cycle_next":         t("Cycle through windows"),
    "dsp.window.move":               t("Move window"),
    "dsp.focus":                     t("Change focus"),
    "dsp.group.toggle":              t("Toggle window group"),
    "dsp.group.next":                t("Next window in group"),
    "dsp.group.prev":                t("Previous window in group"),
    "dsp.group.lock_active":         t("Lock active group"),
    "dsp.workspace.toggle_special":  t("Toggle special workspace"),
}

# hl.dsp.global("caelestia:...") → what it does
CAELESTIA_GLOBALS = {
    "caelestia:launcher":         t("Open app launcher"),
    "caelestia:session":          t("Session and power menu"),
    "caelestia:sidebar":          t("Toggle sidebar"),
    "caelestia:clearNotifs":      t("Clear notifications"),
    "caelestia:showall":          t("Show all panels"),
    "caelestia:lock":             t("Lock screen"),
    "caelestia:screenshot":       t("Screenshot a region"),
    "caelestia:screenshotFreeze": t("Screenshot (frozen screen)"),
    "caelestia:brightnessUp":     t("Brightness up"),
    "caelestia:brightnessDown":   t("Brightness down"),
    "caelestia:mediaToggle":      t("Play / pause media"),
    "caelestia:mediaNext":        t("Next track"),
    "caelestia:mediaPrev":        t("Previous track"),
    "caelestia:mediaStop":        t("Stop media"),
}

# fn.toggle("<special workspace>") → what it does
SPECIAL_WS_LABELS = {
    "specialws":     t("Toggle special workspace"),
    "sysmon":        t("Toggle system monitor workspace"),
    "music":         t("Toggle music workspace"),
    "communication": t("Toggle communication workspace"),
    "todo":          t("Toggle to-do workspace"),
}

# Anonymous Lua function → what it does (keyed by the variable it was bound to)
ANON_FN_LABELS = {
    "kbRestoreLock":     t("Restart the shell and lock the screen"),
    "kbWindowPip":       t("Picture-in-picture the active window"),
    "kbNormalizeWindow": t("Reset window size and center it"),
}

_lua_desc_cache: dict = {}


def _normalise_combo(combo: str) -> frozenset:
    """Order- and case-insensitive key so "CTRL + SUPER + R" == "SUPER + CTRL + R"."""
    parts = (p.strip().upper() for p in combo.split("+"))
    return frozenset(p for p in parts if p)


def _humanise_var(name: str) -> str:
    name = re.sub(r"^kb", "", name)
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", name)
    return " ".join(words) if words else name


def _format_args(arg: str) -> str:
    if not arg or arg == "nil":
        return ""
    if arg.startswith("{") and arg.endswith("}"):
        return arg[1:-1]
    return arg


# Raw dispatcher arguments → friendlier wording. Unknown parts are kept as-is.
ARG_KEYWORDS = {
    "direction=left":    t("left"),
    "direction=right":   t("right"),
    "direction=up":      t("up"),
    "direction=down":    t("down"),
    "workspace=+1":      t("next workspace"),
    "workspace=-1":      t("previous workspace"),
    "workspace=+10":     t("next workspace group"),
    "workspace=-10":     t("previous workspace group"),
    "out_of_group=true": t("out of its group"),
    "next=false":        t("backwards"),
    "mode=maximized":    t("maximized"),
    "mode=fullscreen":   t("fullscreen"),
}

def _pretty_args(arg: str) -> str:
    raw = _format_args(arg)
    if not raw:
        return ""
    if "=" not in raw:
        return raw
    parts = []
    for part in raw.split(","):
        key, _, value = part.partition("=")
        if key == "workspace" and value.startswith("e+"):
            # Hyprland's "take the window back from the special workspace"
            parts.append(t("out of the special workspace"))
        else:
            parts.append(ARG_KEYWORDS.get(part, part))
    return ", ".join(parts)


def _describe_dsp(path: str, arg: str) -> str:
    if path == "dsp.exec_cmd":
        return f"{t('Run')}: {arg}" if arg else t("Run a command")
    if path == "dsp.global":
        return CAELESTIA_GLOBALS.get(arg, f"{t('Caelestia shortcut')}: {arg}")

    if path == "dsp.window.fullscreen":
        return t("Toggle maximized") if "mode=maximized" in arg else t("Toggle fullscreen")
    if path == "dsp.window.cycle_next" and "next=false" in arg:
        return t("Cycle through windows backwards")
    if path == "dsp.window.move" and "out_of_group=true" in arg:
        return t("Move window out of its group")

    label = ACTION_LABELS.get(path) or path.replace("dsp.", "").replace(".", " ")
    pretty = _pretty_args(arg)
    return f"{label} ({pretty})" if pretty else label


def _describe_fn(path: str, arg: str) -> str:
    args = arg.split(",") if arg else []
    if path == "toggle":
        ws = args[0] if args else ""
        return SPECIAL_WS_LABELS.get(ws, t("Toggle {ws} workspace").replace("{ws}", ws))
    if path == "wsaction":
        action = args[0] if args else ""
        range_ = args[1] if len(args) > 1 else ""
        idx = args[2] if len(args) > 2 else ""
        verb = t("Move window to workspace") if action == "move" else t("Go to workspace")
        text = f"{verb} {idx}".strip()
        return f"{text} {t('(group)')}" if range_ == "group" else text
    if path == "resize_active_window":
        try:
            x, y = int(args[0]), int(args[1])
        except (IndexError, ValueError):
            return t("Resize the active window")
        bits = []
        if x:
            bits.append(t("wider") if x > 0 else t("narrower"))
        if y:
            bits.append(t("taller") if y > 0 else t("shorter"))
        base = t("Resize the active window")
        return f"{base} ({', '.join(bits)})" if bits else base
    if path == "resize_by_screen" and len(args) >= 2:
        return t("Resize window to {x}% × {y}% of the screen").replace("{x}", args[0]).replace("{y}", args[1])
    if path == "resize_by_screen":
        return t("Resize window to a fraction of the screen")
    if path == "resizer":
        return t("Resize window")
    if path == "move_actions":
        return t("Move window to picture-in-picture")
    return f"{path}({arg})" if arg else f"{path}()"


def _describe_entry(kind: str, path: str, arg: str, var: str) -> str:
    if kind == "dsp":
        return _describe_dsp(path, arg)
    if kind == "fn":
        return _describe_fn(path, arg)
    if kind == "anon":
        if var in ANON_FN_LABELS:
            return ANON_FN_LABELS[var]
        if var:
            return _humanise_var(var)
        return t("Lua function") + (f" ({path})" if path else "")
    return f"{path}({arg})" if arg else path


def _run_lua_dump(files: list[Path]) -> dict:
    """Evaluate the Lua config with a stub hl table and return combo → info."""
    lua = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
    if not lua:
        return {}

    script = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as fh:
            fh.write(_LUA_DUMP_SCRIPT)
            script = fh.name
        res = subprocess.run(
            [lua, script, *[str(p) for p in files]],
            capture_output=True, text=True, timeout=5,
        )
        stdout = res.stdout
    except Exception as e:
        print(f"Lua-Bind-Dump fehler: {e}")
        return {}
    finally:
        if script:
            try:
                os.unlink(script)
            except OSError:
                pass

    result: dict = {}
    for line in stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 4:
            continue
        key, kind, path, arg = fields[0], fields[1], fields[2], fields[3]
        var = fields[4] if len(fields) > 4 else ""
        if not key:
            continue
        description = _describe_entry(kind, path, arg, var)
        if not description:
            continue
        raw = f"{path} {arg}".strip() if kind != "anon" else path
        # Later definitions win — they are the ones Hyprland registers last.
        result[_normalise_combo(key)] = {"description": description, "raw": raw}
    return result


def _lua_bind_descriptions() -> dict:
    """combo → {"description", "raw"} for every hl.bind() in the Lua config."""
    files = [p for p in LUA_BIND_FILES if p.exists()]
    if not files:
        return {}
    try:
        cache_key = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    except OSError:
        return {}
    if _lua_desc_cache.get("key") == cache_key:
        return _lua_desc_cache.get("map", {})

    result = _run_lua_dump(files)
    _lua_desc_cache["key"] = cache_key
    _lua_desc_cache["map"] = result
    return result


def _parse_hyprctl_binds() -> list[dict]:
    try:
        res = subprocess.run(["hyprctl", "-j", "binds"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            items = json.loads(res.stdout)
            bind_descriptions = _lua_bind_descriptions() if is_lua_mode() else {}
            binds = []
            for i, item in enumerate(items):
                mask = item.get("modmask", 0)
                mods = []
                if mask & 64: mods.append("SUPER")
                if mask & 4: mods.append("CTRL")
                if mask & 8: mods.append("ALT")
                if mask & 1: mods.append("SHIFT")
                mod_str = " ".join(mods)

                btype = "bind"
                if item.get("repeat"): btype = "binde"
                elif item.get("release"): btype = "bindr"
                elif item.get("locked"): btype = "bindl"
                elif item.get("mouse"): btype = "bindm"

                dispatcher = item.get("dispatcher", "")
                argument = item.get("arg", "")

                # "__lua 212" tells nothing — look up what the key actually does.
                description = ""
                description_raw = ""
                if dispatcher == "__lua":
                    combo = " + ".join([*mods, item.get("key", "")]).strip(" +")
                    info = bind_descriptions.get(_normalise_combo(combo))
                    if info:
                        description = info["description"]
                        description_raw = info["raw"]

                binds.append({
                    "id":                f"hyprctl_{i}",
                    "line_number":       i,
                    "raw_line":          f"{btype} = {mod_str}, {item.get('key', '')}, {dispatcher}, {argument}",
                    "bind_type":         btype,
                    "modifier_raw":      mod_str,
                    "modifier_resolved": mod_str,
                    "key_raw":           item.get("key", ""),
                    "key_resolved":      item.get("key", ""),
                    "dispatcher":        dispatcher,
                    "argument":          argument,
                    "comment":           item.get("description", ""),
                    "description":       description,
                    "description_raw":   description_raw,
                    "source":            "hyprctl",
                    "enabled":           True,
                    "submap":            item.get("submap", ""),
                })
            return binds
    except Exception as e:
        print(f"hyprctl binds error: {e}")
    return []


def parse_keybinds() -> list[dict]:
    if is_lua_mode():
        binds = []
        if CAELESTIA_KEYBINDS_LUA.exists():
            try:
                lines = CAELESTIA_KEYBINDS_LUA.read_text().splitlines()
                for i, line in enumerate(lines):
                    sline = line.strip()
                    if not sline:
                        continue
                    disabled = sline.startswith("--")
                    if disabled:
                        sline = sline.lstrip("-").strip()
                        if not sline:
                            continue
                    if "@cs-meta:" in sline:
                        try:
                            meta_part = sline.split("@cs-meta:", 1)[1].strip()
                            data = json.loads(meta_part)
                            btype = data.get("bind_type", "bind")
                            mod = data.get("modifier", "")
                            key = data.get("key", "")
                            disp = data.get("dispatcher", "")
                            arg = data.get("argument", "")
                            comment = data.get("comment", "")
                            binds.append({
                                "id":                f"bind_{i}",
                                "line_number":       i,
                                "raw_line":          line,
                                "bind_type":         btype.lower(),
                                "modifier_raw":      mod,
                                "modifier_resolved": mod,
                                "key_raw":           key,
                                "key_resolved":      key,
                                "dispatcher":        disp,
                                "argument":          arg,
                                "comment":           comment,
                                "source":            "lua_user",
                                "enabled":           not disabled,
                                "submap":            data.get("submap", ""),
                            })
                            continue
                        except Exception:
                            pass

                    m = re.match(r'hl\.bind\s*\(\s*["\']([^"\']+)["\']\s*,\s*([^,\)]+)(?:,\s*([^)]+))?\)', sline)
                    if m:
                        combo_str, action_str, flags_str = m.groups()
                        combo_parts = [p.strip() for p in combo_str.split("+")]
                        key = combo_parts[-1] if combo_parts else ""
                        mod = " + ".join(combo_parts[:-1])
                        disp = "exec"
                        arg = ""
                        exec_m = re.search(r'hl\.dsp\.exec_cmd\s*\(\s*["\']([^"\']+)["\']\s*\)', action_str)
                        if exec_m:
                            arg = exec_m.group(1)
                        else:
                            disp_m = re.search(r'hl\.dispatch\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']+)["\'])?\s*\)', action_str)
                            if disp_m:
                                disp = disp_m.group(1)
                                arg = disp_m.group(2) or ""
                        btype = "bind"
                        if flags_str:
                            if "repeating" in flags_str: btype = "binde"
                            elif "release" in flags_str: btype = "bindr"
                            elif "locked" in flags_str: btype = "bindl"
                            elif "mouse" in flags_str: btype = "bindm"
                        binds.append({
                            "id":                f"bind_{i}",
                            "line_number":       i,
                            "raw_line":          line,
                            "bind_type":         btype,
                            "modifier_raw":      mod,
                            "modifier_resolved": mod,
                            "key_raw":           key,
                            "key_resolved":      key,
                            "dispatcher":        disp,
                            "argument":          arg,
                            "comment":           "",
                            "source":            "lua_user",
                            "enabled":           not disabled,
                            "submap":            "",
                        })
            except Exception as e:
                print(f"Keybinds Lua-Parser error: {e}")

        # Also load system binds from hyprctl to show all active bindings
        live_binds = _parse_hyprctl_binds()
        user_combos = {
            f"{b['modifier_raw']}+{b['key_raw']}".strip("+").lower()
            for b in binds
            if b.get("enabled", True)
        }
        for lb in live_binds:
            combo = f"{lb['modifier_raw']}+{lb['key_raw']}".strip("+").lower()
            if combo not in user_combos:
                binds.append(lb)
        return binds

    # Classic .conf mode
    if not KEYBINDS_CONF.exists():
        return []
    variables = _parse_variables(VARIABLES_CONF)
    binds = []
    try:
        lines = KEYBINDS_CONF.read_text().splitlines()
        for i, line in enumerate(lines):
            m = BIND_RE.match(line)
            if not m:
                continue
            _, btype, mod_raw, key_raw, disp, arg, comment = m.groups()
            mod_raw = mod_raw.strip()
            key_raw = key_raw.strip()
            binds.append({
                "id":                f"bind_{i}",
                "line_number":       i,
                "raw_line":          line,
                "bind_type":         btype.lower(),
                "modifier_raw":      mod_raw,
                "modifier_resolved": _resolve(mod_raw, variables),
                "key_raw":           key_raw,
                "key_resolved":      _resolve(key_raw, variables),
                "dispatcher":        (disp or "").strip(),
                "argument":          (arg or "").strip(),
                "comment":           (comment or "").strip(),
                "enabled":           True,
                "submap":            "",
            })
    except Exception as e:
        print(f"Keybinds-Parser fehler: {e}")
    return binds


def _backup():
    target = get_keybinds_path()
    if target.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(target, target.with_suffix(f".bak_{ts}{target.suffix}"))


def _build_line(data: dict) -> str:
    line = f"{data['bind_type']} = {data['modifier']}, {data['key']}, {data['dispatcher']}"
    if data.get("argument"):
        line += f", {data['argument']}"
    if data.get("comment"):
        line += f"  # {data['comment']}"
    return line


def _lua_action(disp: str, arg: str) -> str | None:
    """Translate a legacy Hyprland dispatcher into the Lua dispatcher API.

    Hyprland 0.56 removed the old ``hl.dispatch("name", "arg")`` form.  Writing
    that form produced a keybind file that failed to load, so map the
    dispatchers exposed by the editor to their ``hl.dsp`` equivalents.
    Returns ``None`` for dispatchers that have no direct Lua equivalent.
    """
    def q(value) -> str:
        return json.dumps(str(value))
    d = disp.lower().strip()
    a = arg.strip()

    if d == "exec":
        return f"hl.dsp.exec_cmd({q(a)})"
    if d in ("killactive", "closewindow"):
        return "hl.dsp.window.close()"
    if d == "workspace":
        return f"hl.dsp.focus({{ workspace = {q(a)} }})" if a else None
    if d == "movetoworkspace":
        return f"hl.dsp.window.move({{ workspace = {q(a)} }})" if a else None
    if d == "movetoworkspacesilent":
        return f"hl.dsp.window.move({{ workspace = {q(a)}, silent = true }})" if a else None
    if d == "togglefloating":
        return 'hl.dsp.window.float({ action = "toggle" })'
    if d == "fullscreen":
        mode = {"0": "fullscreen", "1": "maximized", "2": "fullscreen"}.get(a, a or "fullscreen")
        return f"hl.dsp.window.fullscreen({{ mode = {q(mode)} }})"
    if d == "dpms":
        return f"hl.dsp.dpms({{ action = {q(a or 'toggle')} }})"
    if d == "pin":
        return "hl.dsp.window.pin()"
    if d == "movefocus":
        return f"hl.dsp.focus({{ direction = {q(a)} }})" if a else None
    if d == "movewindow":
        return f"hl.dsp.window.move({{ direction = {q(a)} }})" if a else None
    if d == "resizewindow":
        return "hl.dsp.window.resize()"
    if d == "resizeactive":
        if "keepaspect" in a.lower():
            return "hl.dsp.window.resize({ keep_aspect_ratio = true })"
        numbers = re.findall(r"-?\d+(?:\.\d+)?", a)
        if len(numbers) >= 2:
            return f"hl.dsp.window.resize({{ x = {numbers[0]}, y = {numbers[1]} }})"
        return None
    if d == "cyclenext":
        if a == "prev":
            return "hl.dsp.window.cycle_next({ prev = true })"
        if a == "last":
            return "hl.dsp.window.cycle_next({ last = true })"
        return "hl.dsp.window.cycle_next({ next = true })"
    if d == "swapnext":
        return "hl.dsp.window.swap({ prev = true })" if a == "prev" else "hl.dsp.window.swap({ next = true })"
    if d == "focuswindow":
        return f"hl.dsp.focus({{ window = {q(a)} }})" if a else None
    if d == "focusmonitor":
        return f"hl.dsp.focus({{ monitor = {q(a)} }})" if a else None
    if d == "splitratio":
        return f"hl.dsp.layout({q('splitratio ' + a)})" if a else None
    if d == "toggleopaque":
        return 'hl.dsp.window.set_prop({ prop = "opaque", value = "toggle" })'
    if d == "movecursortocorner":
        corner = int(a) if a.isdigit() else 0
        return f"hl.dsp.cursor.move_to_corner({{ corner = {corner} }})"
    if d == "exit":
        return "hl.dsp.exit()"
    if d == "forcerendererreload":
        return "hl.dsp.force_renderer_reload()"
    if d == "movecurrentworkspacetomonitor":
        return f"hl.dsp.workspace.move({{ monitor = {q(a)} }})" if a else None
    if d == "focusworkspaceoncurrentmonitor":
        return f"hl.dsp.focus({{ workspace = {q(a)}, monitor = 'current' }})" if a else None
    if d == "togglespecialworkspace":
        return f"hl.dsp.workspace.toggle_special({q(a)})" if a else "hl.dsp.workspace.toggle_special()"
    if d == "swapactiveworkspaces":
        monitors = a.split()
        if len(monitors) >= 2:
            return f"hl.dsp.workspace.swap_monitors({{ monitor1 = {q(monitors[0])}, monitor2 = {q(monitors[1])} }})"
        return None
    if d == "bringactivetotop":
        return "hl.dsp.window.bring_to_top()"
    if d == "alterzorder":
        return f"hl.dsp.window.alter_zorder({{ mode = {q(a or 'top')} }})"
    if d == "togglesplit":
        return 'hl.dsp.layout("togglesplit")'
    if d == "layoutmsg":
        return f"hl.dsp.layout({q(a)})" if a else None
    if d == "global":
        return f"hl.dsp.global({q(a)})" if a else None
    if d == "submap":
        return f"hl.dsp.submap({q(a)})" if a else None
    if d == "moveoutofgroup":
        return "hl.dsp.window.move({ out_of_group = true })"
    if d == "changegroupactive":
        return "hl.dsp.group.prev()" if a == "prev" else "hl.dsp.group.next()"
    if d == "togglegroup":
        return "hl.dsp.group.toggle()"
    if d == "lockactivegroup":
        return "hl.dsp.group.lock_active()"
    if d == "centerwindow":
        return "hl.dsp.window.center()"
    return None


def _build_lua_line(data: dict) -> str:
    combo_parts = []
    mod = data.get("modifier", "").strip()
    key = data.get("key", "").strip()
    if mod:
        combo_parts.append(mod)
    if key:
        combo_parts.append(key)
    combo = " + ".join(combo_parts)

    btype = data.get("bind_type", "bind").lower()
    disp = data.get("dispatcher", "exec").strip()
    arg = data.get("argument", "").strip()
    comment = data.get("comment", "").strip()

    action = _lua_action(disp, arg)
    if action is None:
        raise ValueError(
            t("The dispatcher {name} is not supported in Lua mode.").format(name=disp)
        )

    flags_map = {
        "binde": "{ repeating = true }",
        "bindl": "{ locked = true }",
        "bindle": "{ locked = true, repeating = true }",
        "bindr": "{ release = true }",
        "bindm": "{ mouse = true }",
        "bindi": "{ ignore_inhibit = true }",
        "bindin": "{ ignore_inhibit = true, non_consuming = true }",
    }
    flags = flags_map.get(btype, "")
    meta_json = json.dumps(data)
    if flags:
        code = f'hl.bind("{combo}", {action}, {flags})'
    else:
        code = f'hl.bind("{combo}", {action})'

    if comment:
        return f"{code} -- {comment} | @cs-meta:{meta_json}"
    return f"{code} -- @cs-meta:{meta_json}"


def _find_line(lines: list[str], line_number: int, raw_line: str | None) -> int | None:
    """Returns the actual index for the line, re-searching by content if the file changed."""
    if raw_line is not None:
        if 0 <= line_number < len(lines) and lines[line_number].strip() == raw_line.strip():
            return line_number
        for i, line in enumerate(lines):
            if line.strip() == raw_line.strip():
                return i
        return None
    return line_number if 0 <= line_number < len(lines) else None


def save_keybind(data: dict, line_number: int | None = None, raw_line: str | None = None):
    _backup()
    if is_lua_mode():
        ensure_hypr_user_lua()
        CAELESTIA_KEYBINDS_LUA.parent.mkdir(parents=True, exist_ok=True)
        lines = CAELESTIA_KEYBINDS_LUA.read_text().splitlines() if CAELESTIA_KEYBINDS_LUA.exists() else []
        new_line = _build_lua_line(data)
        idx = _find_line(lines, line_number, raw_line) if (line_number is not None and raw_line is not None) else None
        if idx is not None:
            lines[idx] = new_line
        else:
            lines.append(new_line)
        CAELESTIA_KEYBINDS_LUA.write_text("\n".join(lines) + "\n")
        hyprctl_reload()
        return

    # Classic mode
    KEYBINDS_CONF.parent.mkdir(parents=True, exist_ok=True)
    if not KEYBINDS_CONF.exists():
        KEYBINDS_CONF.touch()
    new_line = _build_line(data)
    lines = KEYBINDS_CONF.read_text().splitlines()
    if line_number is not None:
        idx = _find_line(lines, line_number, raw_line)
        if idx is not None:
            lines[idx] = new_line
        else:
            lines.append(new_line)
    else:
        lines.append(new_line)
    KEYBINDS_CONF.write_text("\n".join(lines) + "\n")
    hyprctl_reload()


def delete_keybind(line_number: int, raw_line: str | None = None, bind_data: dict | None = None):
    _backup()
    if is_lua_mode():
        if CAELESTIA_KEYBINDS_LUA.exists():
            lines = CAELESTIA_KEYBINDS_LUA.read_text().splitlines()
            idx = _find_line(lines, line_number, raw_line)
            if idx is not None:
                lines.pop(idx)
                CAELESTIA_KEYBINDS_LUA.write_text("\n".join(lines) + "\n")
                hyprctl_reload()
                return

        # If it was a system bind not directly in user-keybinds.lua, issue an unbind
        if bind_data:
            mod = bind_data.get("modifier_raw", "").strip()
            key = bind_data.get("key_raw", "").strip()
            combo = f"{mod} + {key}" if mod else key
            CAELESTIA_KEYBINDS_LUA.parent.mkdir(parents=True, exist_ok=True)
            with open(CAELESTIA_KEYBINDS_LUA, "a") as f:
                f.write(f'hl.unbind("{combo}")\n')
            ensure_hypr_user_lua()
            hyprctl_reload()
        return

    # Classic mode
    lines = KEYBINDS_CONF.read_text().splitlines()
    idx = _find_line(lines, line_number, raw_line)
    if idx is not None:
        lines.pop(idx)
        KEYBINDS_CONF.write_text("\n".join(lines) + "\n")
    hyprctl_reload()


def set_keybind_enabled(bind: dict, enabled: bool) -> bool:
    """Enable/disable a user Lua bind by commenting its line."""
    if not is_lua_mode() or bind.get("source") != "lua_user":
        return False
    if not CAELESTIA_KEYBINDS_LUA.exists():
        return False
    _backup()
    lines = CAELESTIA_KEYBINDS_LUA.read_text().splitlines()
    idx = _find_line(lines, bind.get("line_number", -1), bind.get("raw_line"))
    if idx is None:
        return False
    line = lines[idx]
    if enabled:
        lines[idx] = line.lstrip().lstrip("-").lstrip()
    else:
        if not line.lstrip().startswith("--"):
            lines[idx] = "-- " + line
    atomic_write_text(CAELESTIA_KEYBINDS_LUA, "\n".join(lines) + "\n")
    hyprctl_reload()
    return True


# ── Keybind-Dialog ────────────────────────────────────────────────────────────

class KeybindDialog(Gtk.Dialog):
    """Kompakter Dialog im Grid-Layout — kein zerhacktes ActionRow-Design."""

    def __init__(self, parent, bind: dict | None = None):
        super().__init__(
            title=t("Edit keybind") if bind else t("New keybind"),
            transient_for=parent,
            modal=True,
        )
        self._line_number = bind["line_number"] if bind else None
        self.set_default_size(480, -1)

        self.add_button(t("Cancel"), Gtk.ResponseType.CANCEL)
        save_btn = self.add_button(t("Save"), Gtk.ResponseType.OK)
        save_btn.add_css_class("suggested-action")
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(12)
        grid.set_margin_top(16); grid.set_margin_bottom(16)
        grid.set_margin_start(16); grid.set_margin_end(16)

        def _lbl(text, row):
            lbl = Gtk.Label(label=text)
            lbl.set_halign(Gtk.Align.END)
            lbl.add_css_class("dim-label")
            grid.attach(lbl, 0, row, 1, 1)

        # Bind-Typ
        _lbl(t("Bind type"), 0)
        self._type_combo = Gtk.ComboBoxText()
        self._type_combo.set_hexpand(True)
        for bt, label in BIND_TYPE_LABELS.items():
            self._type_combo.append(bt, f"{bt} — {label}")
        self._type_combo.set_active_id(bind["bind_type"] if bind else "bind")
        grid.attach(self._type_combo, 1, 0, 1, 1)

        # Modifier
        _lbl(t("Modifier"), 1)
        self._mod_entry = Gtk.Entry()
        self._mod_entry.set_hexpand(True)
        self._mod_entry.set_placeholder_text(t("SUPER, CTRL SHIFT, $mainMod …"))
        self._mod_entry.set_text(bind["modifier_raw"] if bind else "SUPER")
        grid.attach(self._mod_entry, 1, 1, 1, 1)

        # Taste
        _lbl(t("Key"), 2)
        key_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._key_entry = Gtk.Entry()
        self._key_entry.set_hexpand(True)
        self._key_entry.set_placeholder_text(t("T, Return, F1, mouse:272 …"))
        self._key_entry.set_text(bind["key_raw"] if bind else "")
        key_box.append(self._key_entry)
        record_btn = Gtk.Button(icon_name="media-record-symbolic")
        record_btn.set_tooltip_text(t("Record a shortcut"))
        record_btn.connect("clicked", lambda _b: self._record_shortcut())
        key_box.append(record_btn)
        grid.attach(key_box, 1, 2, 1, 1)

        # Dispatcher
        _lbl(t("Dispatcher"), 3)
        self._disp_combo = Gtk.ComboBoxText()
        self._disp_combo.set_hexpand(True)
        for d in DISPATCHERS:
            self._disp_combo.append(d, d)
        self._disp_combo.set_active_id(bind["dispatcher"] if bind else "exec")
        grid.attach(self._disp_combo, 1, 3, 1, 1)

        # Argument
        _lbl(t("Argument"), 4)
        self._arg_entry = Gtk.Entry()
        self._arg_entry.set_hexpand(True)
        self._arg_entry.set_placeholder_text(t("optional — kitty, 1, toggle …"))
        self._arg_entry.set_text(bind["argument"] if bind else "")
        grid.attach(self._arg_entry, 1, 4, 1, 1)

        # Kommentar
        _lbl(t("Comment"), 5)
        self._comment_entry = Gtk.Entry()
        self._comment_entry.set_hexpand(True)
        self._comment_entry.set_placeholder_text(t("optional"))
        self._comment_entry.set_text(bind["comment"] if bind else "")
        grid.attach(self._comment_entry, 1, 5, 1, 1)

        self.get_content_area().append(grid)
        self._key_entry.connect("activate", lambda _: self.response(Gtk.ResponseType.OK))
        self._arg_entry.connect("activate", lambda _: self.response(Gtk.ResponseType.OK))

    def _record_shortcut(self) -> None:
        dialog = Gtk.Dialog(
            title=t("Record shortcut"),
            transient_for=self,
            modal=True,
        )
        dialog.set_default_size(420, 130)
        dialog.add_button(t("Cancel"), Gtk.ResponseType.CANCEL)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)
        label = Gtk.Label(label=t("Press a key combination…"))
        label.add_css_class("title-4")
        box.append(label)
        hint = Gtk.Label(label=t("Keyboard only. Type mouse:272 manually for mouse binds."))
        hint.add_css_class("dim-label")
        box.append(hint)
        dialog.get_content_area().append(box)

        modifier_keys = {
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Super_L", "Super_R", "Meta_L", "Meta_R", "Hyper_L", "Hyper_R",
            "Caps_Lock", "Num_Lock", "ISO_Level3_Shift",
        }
        key_names = {
            "space": "Space",
            "Return": "Return",
            "Escape": "Escape",
            "BackSpace": "BackSpace",
            "Tab": "Tab",
            "ISO_Left_Tab": "Tab",
            "Delete": "Delete",
            "Insert": "Insert",
            "Home": "Home",
            "End": "End",
            "Page_Up": "Page_Up",
            "Page_Down": "Page_Down",
            "Up": "Up",
            "Down": "Down",
            "Left": "Left",
            "Right": "Right",
            "Menu": "Menu",
            "Print": "Print",
            "Pause": "Pause",
            "Scroll_Lock": "Scroll_Lock",
        }

        def on_key(_controller, keyval, _keycode, state) -> bool:
            name = Gdk.Keyval.name(keyval)
            if name in modifier_keys:
                return False
            mods = []
            if state & Gdk.ModifierType.CONTROL_MASK:
                mods.append("CTRL")
            if state & Gdk.ModifierType.MOD1_MASK:
                mods.append("ALT")
            if state & Gdk.ModifierType.SHIFT_MASK:
                mods.append("SHIFT")
            super_mask = int(getattr(Gdk.ModifierType, "SUPER_MASK", 1 << 26))
            mod4_mask = int(getattr(Gdk.ModifierType, "MOD4_MASK", 1 << 6))
            if state & (super_mask | mod4_mask):
                mods.append("SUPER")
            key = key_names.get(name, name.upper() if len(name) == 1 else name)
            self._mod_entry.set_text(" ".join(mods))
            self._key_entry.set_text(key)
            dialog.destroy()
            return True

        controller = Gtk.EventControllerKey.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", on_key)
        dialog.add_controller(controller)
        dialog.present()

    def get_data(self) -> dict:
        return {
            "bind_type":  self._type_combo.get_active_id() or "bind",
            "modifier":   self._mod_entry.get_text().strip(),
            "key":        self._key_entry.get_text().strip(),
            "dispatcher": self._disp_combo.get_active_id() or "exec",
            "argument":   self._arg_entry.get_text().strip(),
            "comment":    self._comment_entry.get_text().strip(),
        }

    @property
    def line_number(self) -> int | None:
        return self._line_number


# ── Haupt-Seite ───────────────────────────────────────────────────────────────

class KeybindsPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self._all_binds: list[dict] = []
        self._conflicts: dict[tuple[str, str], list[dict]] = {}

        # ── Toolbar ──────────────────────────────────────────────────────
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_margin_top(12); bar.set_margin_bottom(8)
        bar.set_margin_start(12); bar.set_margin_end(12)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(t("Search: SUPER, exec, kitty..."))
        self._search.set_hexpand(True)
        self._search.connect("search-changed", lambda _: self._filter())
        bar.append(self._search)

        self._type_filter = Gtk.ComboBoxText()
        self._type_filter.append("", t("All types"))
        for bt in BIND_TYPE_LABELS:
            self._type_filter.append(bt, bt)
        self._type_filter.set_active(0)
        self._type_filter.connect("changed", lambda _: self._filter())
        bar.append(self._type_filter)

        self._submap_filter = Gtk.ComboBoxText()
        self._submap_filter.append("", t("All submaps"))
        self._submap_filter.set_active(0)
        self._submap_filter.connect("changed", lambda _: self._filter())
        bar.append(self._submap_filter)

        self._conflict_btn = Gtk.Button(label=t("No conflicts"))
        self._conflict_btn.add_css_class("pill")
        self._conflict_btn.set_visible(False)
        self._conflict_btn.connect("clicked", lambda _b: self._show_conflicts())
        bar.append(self._conflict_btn)

        export_btn = Gtk.Button(label=t("Export"))
        export_btn.set_tooltip_text(t("Export a Markdown cheat sheet"))
        export_btn.connect("clicked", lambda _b: self._export_cheatsheet())
        bar.append(export_btn)

        add_btn = Gtk.Button(label=t("+ New"))
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add)
        bar.append(add_btn)

        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._load())
        bar.append(reload_btn)

        self._count_label = Gtk.Label()
        self._count_label.add_css_class("caption")
        self._count_label.add_css_class("dim-label")
        bar.append(self._count_label)
        self.append(bar)

        # Pfad
        self._path_label = Gtk.Label()
        self._path_label.set_markup(
            f"<small><tt>{str(get_keybinds_path()).replace(str(Path.home()), '~')}</tt></small>"
        )
        self._path_label.add_css_class("dim-label")
        self._path_label.set_halign(Gtk.Align.CENTER)
        self._path_label.set_margin_bottom(6)
        self.append(self._path_label)

        # ── Liste ─────────────────────────────────────────────────────────
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_top(4); self._list_box.set_margin_bottom(12)
        self._list_box.set_margin_start(12); self._list_box.set_margin_end(12)
        scroller.set_child(self._list_box)

        self._empty = Adw.StatusPage()
        self._empty.set_icon_name("preferences-desktop-keyboard-symbolic")
        self._empty.set_title(t("No keybinds found"))
        self._empty.set_description(
            t("Check your keybinds.conf or add a new keybind.")
        )
        self._empty.set_vexpand(True)
        self._empty.set_visible(False)
        self.append(self._empty)

        self._load()

    def _load(self):
        self._path_label.set_markup(
            f"<small><tt>{str(get_keybinds_path()).replace(str(Path.home()), '~')}</tt></small>"
        )
        self._all_binds = parse_keybinds()
        self._refresh_submap_filter()
        self._conflicts = self._detect_conflicts()
        self._update_conflict_button()
        self._filter()

    def _refresh_submap_filter(self) -> None:
        current = self._submap_filter.get_active_id() or ""
        self._submap_filter.remove_all()
        self._submap_filter.append("", t("All submaps"))
        for submap in sorted({b.get("submap", "") for b in self._all_binds if b.get("submap")}):
            self._submap_filter.append(submap, submap)
        if not self._submap_filter.set_active_id(current):
            self._submap_filter.set_active(0)

    def _detect_conflicts(self) -> dict[tuple[str, str], list[dict]]:
        groups: dict[tuple[str, str], list[dict]] = {}
        for bind in self._all_binds:
            if not bind.get("enabled", True):
                continue
            combo = (
                bind.get("modifier_resolved") or bind.get("modifier_raw", ""),
                bind.get("key_resolved") or bind.get("key_raw", ""),
            )
            groups.setdefault(combo, []).append(bind)
        return {combo: items for combo, items in groups.items() if len(items) > 1}

    def _update_conflict_button(self) -> None:
        count = len(self._conflicts)
        self._conflict_btn.set_visible(count > 0)
        self._conflict_btn.set_label(t("⚠ {count} conflict(s)").format(count=count))

    def _show_conflicts(self) -> None:
        lines = []
        for (mod, key), binds in sorted(self._conflicts.items()):
            combo = f"{mod} + {key}".strip(" +")
            actions = " | ".join(
                f"{b.get('dispatcher', '?')} {b.get('argument', '')}".strip() for b in binds
            )
            lines.append(f"• {combo}: {actions}")
        dialog = Adw.AlertDialog(heading=t("Keybind conflicts"), body="\n".join(lines) or t("None"))
        dialog.add_response("close", t("Close"))
        dialog.present(self.main_window)

    def _filter(self):
        q  = self._search.get_text().lower()
        bt = self._type_filter.get_active_id() or ""
        submap = self._submap_filter.get_active_id() or ""

        filtered = [
            b for b in self._all_binds
            if (not q or q in " ".join([
                b["modifier_raw"], b["modifier_resolved"],
                b["key_raw"], b["key_resolved"],
                b["dispatcher"], b["argument"], b["comment"],
                b.get("description", ""), b.get("submap", "")
            ]).lower())
            and (not bt or b["bind_type"] == bt)
            and (not submap or b.get("submap", "") == submap)
        ]

        while row := self._list_box.get_first_child():
            self._list_box.remove(row)

        if not filtered:
            self._list_box.set_visible(False)
            self._empty.set_visible(True)
            self._count_label.set_text(t("0 Keybinds"))
            return

        self._list_box.set_visible(True)
        self._empty.set_visible(False)
        self._count_label.set_text(
            t("{count} Keybind(s)").format(count=len(filtered))
        )

        for bind in filtered:
            self._list_box.append(self._make_row(bind))

    def _make_row(self, bind: dict) -> Adw.ActionRow:
        row = Adw.ActionRow()

        mod = bind["modifier_resolved"] or bind["modifier_raw"]
        key = bind["key_resolved"] or bind["key_raw"]
        row.set_title(f"{mod} + {key}" if mod else key)

        def _esc(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        description = bind.get("description") or ""
        if description:
            sub = _esc(description)
            if bind["comment"]:
                sub += f"  # {_esc(bind['comment'])}"
            # Keep the underlying Lua dispatcher reachable in the tooltip
            raw = bind.get("description_raw") or f"{bind['dispatcher']} {bind['argument']}".strip()
            row.set_tooltip_text(raw)
        else:
            sub = _esc(bind["dispatcher"])
            if bind["argument"]:  sub += f"  {_esc(bind['argument'])}"
            if bind["comment"]:   sub += f"  # {_esc(bind['comment'])}"
        row.set_subtitle(sub)

        if not bind.get("enabled", True):
            row.add_css_class("dim-label")
            disabled = Gtk.Label(label=t("disabled"))
            disabled.add_css_class("caption")
            disabled.add_css_class("warning")
            disabled.set_valign(Gtk.Align.CENTER)
            row.add_suffix(disabled)

        if bind.get("submap"):
            submap_label = Gtk.Label(label=f"submap: {bind['submap']}")
            submap_label.add_css_class("caption")
            submap_label.add_css_class("dim-label")
            submap_label.set_valign(Gtk.Align.CENTER)
            row.add_suffix(submap_label)

        # Bind-Typ Badge
        bt_lbl = Gtk.Label(label=bind["bind_type"])
        bt_lbl.add_css_class("caption"); bt_lbl.add_css_class("dim-label")
        bt_lbl.set_valign(Gtk.Align.CENTER); bt_lbl.set_margin_end(4)
        row.add_suffix(bt_lbl)

        if bind.get("source") == "lua_user":
            enabled_switch = Gtk.Switch()
            enabled_switch.set_valign(Gtk.Align.CENTER)
            enabled_switch.set_active(bind.get("enabled", True))
            enabled_switch.set_tooltip_text(t("Enable or disable this bind"))
            enabled_switch.connect("notify::active", self._on_bind_toggled, bind)
            row.add_suffix(enabled_switch)

        edit_btn = Gtk.Button()
        edit_btn.set_icon_name("document-edit-symbolic")
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.set_tooltip_text(t("Edit"))
        edit_btn.connect("clicked", lambda _, b=bind: self._on_edit(b))
        row.add_suffix(edit_btn)

        del_btn = Gtk.Button()
        del_btn.set_icon_name("user-trash-symbolic")
        del_btn.add_css_class("destructive-action")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.set_tooltip_text(t("Delete"))
        del_btn.connect("clicked", lambda _, b=bind: self._on_delete(b))
        row.add_suffix(del_btn)

        return row

    def _on_bind_toggled(self, switch, _pspec, bind: dict) -> None:
        if not set_keybind_enabled(bind, switch.get_active()):
            self.main_window.add_toast(Adw.Toast.new(t("This bind cannot be disabled here.")))
            self._load()
            return
        self.main_window.add_toast(
            Adw.Toast.new(t("Keybind enabled.") if switch.get_active() else t("Keybind disabled."))
        )
        self._load()

    def _export_cheatsheet(self) -> None:
        dialog = Gtk.FileDialog(title=t("Export keybind cheat sheet"))
        dialog.set_initial_name("caelestia-keybinds.md")
        dialog.save(self.main_window, None, self._on_export_done)

    def _on_export_done(self, dialog, result) -> None:
        try:
            file = dialog.save_finish(result)
        except Exception:
            return
        path = Path(file.get_path())
        lines = ["# Caelestia keybinds", "", "| Shortcut | Action | Type |", "|---|---|---|"]
        for bind in sorted(
            self._all_binds,
            key=lambda b: (
                (b.get("modifier_resolved") or b.get("modifier_raw", "")).lower(),
                (b.get("key_resolved") or b.get("key_raw", "")).lower(),
            ),
        ):
            if not bind.get("enabled", True):
                continue
            mod = bind.get("modifier_resolved") or bind.get("modifier_raw", "")
            key = bind.get("key_resolved") or bind.get("key_raw", "")
            combo = f"{mod} + {key}".strip(" +")
            action = bind.get("description") or f"{bind.get('dispatcher', '')} {bind.get('argument', '')}".strip()
            lines.append(f"| `{combo}` | {action} | {bind.get('bind_type', 'bind')} |")
        try:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.main_window.add_toast(Adw.Toast.new(t("Exported {name}").format(name=path.name)))
        except OSError as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Export failed: {error}").format(error=exc)))

    def _on_add(self, _btn):
        dlg = KeybindDialog(self.main_window)
        dlg.connect("response", self._on_dialog_response, dlg, None, None)
        dlg.present()

    def _on_edit(self, bind: dict):
        dlg = KeybindDialog(self.main_window, bind)
        dlg.connect("response", self._on_dialog_response, dlg, bind["line_number"], bind.get("raw_line"))
        dlg.present()

    def _on_dialog_response(self, dlg, response, dialog_obj, line_number, raw_line):
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        data = dialog_obj.get_data()
        if not data["key"] or not data["dispatcher"]:
            self.main_window.add_toast(
                Adw.Toast.new(t("Key and dispatcher are required."))
            )
            return
        try:
            save_keybind(data, line_number, raw_line)
            self._load()
            self.main_window.add_toast(
                Adw.Toast.new(t("Keybind saved and Hyprland reloaded."))
            )
        except Exception as e:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

    def _on_delete(self, bind: dict):
        mod = bind["modifier_resolved"] or bind["modifier_raw"]
        key = bind["key_resolved"] or bind["key_raw"]
        dlg = Adw.MessageDialog(
            heading=t("Delete keybind?"),
            body=f"{mod} + {key} → {bind['dispatcher']} {bind['argument']}"
        )
        dlg.set_transient_for(self.main_window)
        dlg.add_response("cancel", t("Cancel"))
        dlg.add_response("delete", t("Delete"))
        dlg.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_resp(d, r):
            if r == "delete":
                try:
                    delete_keybind(bind["line_number"], bind.get("raw_line"), bind)
                    self._load()
                    self.main_window.add_toast(Adw.Toast.new(t("Keybind deleted.")))
                except Exception as e:
                    self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

        dlg.connect("response", on_resp)
        dlg.present()