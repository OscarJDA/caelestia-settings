import json
import os
import re
import subprocess
from pathlib import Path

from src.lang import t
import caelestia_core

# ── Paths ──────────────────────────────────────────────────────────────────────
CONFIG_DIR = Path(os.path.expanduser("~/.config/caelestia-settings"))
MONITOR_CONFIG_FILE = CONFIG_DIR / "monitors.json"
WINDOW_RULES_CONFIG_FILE = CONFIG_DIR / "window_rules.json"
APP_DATA_DIR = Path(os.path.expanduser("~/.local/share/caelestia-settings"))

# Hyprland base
HYPR_CONFIG_DIR = Path(os.path.expanduser("~/.config/hypr"))
HYPR_LUA_CONF = HYPR_CONFIG_DIR / "hyprland.lua"
HYPR_CONF = HYPR_CONFIG_DIR / "hyprland.conf"
HYPR_INCLUDES_DIR = HYPR_CONFIG_DIR / "hyprland"

# Classic (.conf) paths
HYPR_INPUT_CONF = HYPR_INCLUDES_DIR / "input.conf"
HYPR_MONITORS_CONF = HYPR_INCLUDES_DIR / "monitors.conf"
HYPR_RULES_CONF = HYPR_INCLUDES_DIR / "rules.conf"
HYPR_KEYBINDS_CONF = HYPR_INCLUDES_DIR / "keybinds.conf"
HYPR_EXECS_CONF = HYPR_INCLUDES_DIR / "execs.conf"

# Caelestia 2.5.0+ (Lua / Quickshell) paths
CAELESTIA_CONFIG_DIR = Path(os.path.expanduser("~/.config/caelestia"))
CAELESTIA_HYPR_USER = CAELESTIA_CONFIG_DIR / "hypr-user.lua"
CAELESTIA_HYPR_VARS = CAELESTIA_CONFIG_DIR / "hypr-vars.lua"
CAELESTIA_MONITORS_LUA = CAELESTIA_CONFIG_DIR / "monitors.lua"
CAELESTIA_RULES_LUA = CAELESTIA_CONFIG_DIR / "rules.lua"
CAELESTIA_KEYBINDS_LUA = CAELESTIA_CONFIG_DIR / "user-keybinds.lua"
# Caelestia's own (system) keybinds — read-only for the app
HYPR_KEYBINDS_LUA = HYPR_INCLUDES_DIR / "keybinds.lua"
CAELESTIA_SHELL_JSON = CAELESTIA_CONFIG_DIR / "shell.json"


def is_lua_mode() -> bool:
    """Returns True if Hyprland is configured via Lua (Caelestia 2.5.0+)."""
    return HYPR_LUA_CONF.exists() or (CAELESTIA_HYPR_USER.exists() and not HYPR_CONF.exists())


def hyprctl_eval(lua_code: str) -> bool:
    """Execute dynamic Lua code in Hyprland when in Lua mode."""
    try:
        res = subprocess.run(
            ["hyprctl", "eval", lua_code],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return res.returncode == 0
    except Exception as e:
        print(f"hyprctl eval error: {e}")
        return False


def hyprctl_reload():
    """Reload Hyprland config."""
    try:
        subprocess.run(["hyprctl", "reload"], capture_output=True, timeout=3)
    except Exception as e:
        print(f"hyprctl reload error: {e}")


def ensure_hypr_user_lua():
    """Ensure ~/.config/caelestia/hypr-user.lua exists and requires Caelestia Settings modules."""
    CAELESTIA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CAELESTIA_HYPR_USER.exists():
        CAELESTIA_HYPR_USER.write_text(
            '-- Caelestia user configuration\n'
            'pcall(require, "monitors")\n'
            'pcall(require, "rules")\n'
            'pcall(require, "user-keybinds")\n'
            'hl.bind("SUPER + I", hl.dsp.exec_cmd("caelestia-settings"))\n'
            'hl.window_rule({ match = { class = "org.caelestia.settings" }, float = true, center = true })\n'
        )
        return

    content = CAELESTIA_HYPR_USER.read_text()
    additions = []
    if 'pcall(require, "monitors")' not in content and 'require("monitors")' not in content:
        additions.append('pcall(require, "monitors")')
    if 'pcall(require, "rules")' not in content and 'require("rules")' not in content:
        additions.append('pcall(require, "rules")')
    if 'pcall(require, "user-keybinds")' not in content and 'require("user-keybinds")' not in content:
        additions.append('pcall(require, "user-keybinds")')
    if "caelestia-settings" not in content:
        additions.append('hl.bind("SUPER + I", hl.dsp.exec_cmd("caelestia-settings"))')
    if "org.caelestia.settings" not in content:
        additions.append('hl.window_rule({ match = { class = "org.caelestia.settings" }, float = true, center = true })')

    if additions:
        with open(CAELESTIA_HYPR_USER, "a") as f:
            f.write("\n-- Caelestia Settings Integration\n" + "\n".join(additions) + "\n")


def get_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_monitor_config():
    try:
        if MONITOR_CONFIG_FILE.exists():
            with open(MONITOR_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden von {MONITOR_CONFIG_FILE}: {e}")
    return {}


def save_monitor_config(config_data):
    try:
        get_config_dir().mkdir(parents=True, exist_ok=True)
        with open(MONITOR_CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"Monitor-Konfiguration gespeichert in {MONITOR_CONFIG_FILE}")
    except Exception as e:
        print(f"Fehler beim Speichern von {MONITOR_CONFIG_FILE}: {e}")


def load_window_rules_config():
    try:
        if WINDOW_RULES_CONFIG_FILE.exists():
            with open(WINDOW_RULES_CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Fehler beim Laden von {WINDOW_RULES_CONFIG_FILE}: {e}")
    return {}


def save_window_rules_config(config_data):
    try:
        get_config_dir().mkdir(parents=True, exist_ok=True)
        with open(WINDOW_RULES_CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=2)
        print(f"Window-Rules gespeichert in {WINDOW_RULES_CONFIG_FILE}")
    except Exception as e:
        print(f"Fehler beim Speichern von {WINDOW_RULES_CONFIG_FILE}: {e}")


def _parse_lua_monitors_file() -> tuple[list[dict], list[dict]]:
    """Parse monitors and workspace rules from ~/.config/caelestia/monitors.lua."""
    monitors = []
    workspaces = []
    if not CAELESTIA_MONITORS_LUA.exists():
        return monitors, workspaces

    try:
        text = CAELESTIA_MONITORS_LUA.read_text()
        # Parse hl.monitor({ ... })
        for m in re.finditer(r"hl\.monitor\s*\(\s*\{([^}]+)\}\s*\)", text):
            body = m.group(1)
            name_m = re.search(r'output\s*=\s*["\']([^"\']+)["\']', body)
            mode_m = re.search(r'mode\s*=\s*["\']([^"\']+)["\']', body)
            pos_m = re.search(r'position\s*=\s*["\']([^"\']+)["\']', body)
            scale_m = re.search(r'scale\s*=\s*([0-9.]+)', body)
            if name_m:
                monitors.append({
                    "name": name_m.group(1),
                    "resolution": mode_m.group(1) if mode_m else "?",
                    "position": pos_m.group(1) if pos_m else "auto",
                    "scale": scale_m.group(1) if scale_m else "1",
                })

        # Parse hl.workspace_rule({ ... })
        for ws in re.finditer(r"hl\.workspace_rule\s*\(\s*\{([^}]+)\}\s*\)", text):
            body = ws.group(1)
            num_m = re.search(r'workspace\s*=\s*["\']?([0-9]+)["\']?', body)
            mon_m = re.search(r'monitor\s*=\s*["\']([^"\']+)["\']', body)
            is_def = "default = true" in body or "default=true" in body
            if num_m:
                workspaces.append({
                    "number": int(num_m.group(1)),
                    "monitor": mon_m.group(1) if mon_m else "",
                    "default": is_def,
                })
    except Exception as e:
        print(f"Fehler beim Parsen von monitors.lua: {e}")

    return monitors, workspaces


def parse_monitors_conf() -> dict:
    """
    Liest Monitore und Workspaces (unterstützt Lua-Modus und .conf-Modus):
    {
      "monitors":  [ {"name": "DP-1", "resolution": "2560x1440@179.95", ...}, ... ],
      "workspaces": [ {"number": 1, "monitor": "DP-1", "default": True}, ... ],
      "workspace_options": [ ("default", "Standard (keine Regel)"), ("1", "WS 1  –  DP-1  ★"), ... ]
    }
    """
    monitors = []
    workspaces = []

    # Check Lua mode first if monitors.lua exists or we are in Lua mode
    if is_lua_mode() and CAELESTIA_MONITORS_LUA.exists():
        monitors, workspaces = _parse_lua_monitors_file()

    # If empty, check monitors.conf
    if not monitors and HYPR_MONITORS_CONF.exists():
        try:
            text = HYPR_MONITORS_CONF.read_text()
            rust_monitors, rust_workspaces = caelestia_core.parse_monitors_conf(text)
            monitors = [
                {
                    "name": m.name,
                    "resolution": m.resolution,
                    "position": m.position,
                    "scale": m.scale,
                }
                for m in rust_monitors
            ]
            workspaces = [
                {"number": w.number, "monitor": w.monitor, "default": w.default}
                for w in rust_workspaces
            ]
        except Exception as e:
            print(f"Fehler beim Parsen von monitors.conf: {e}")

    # Fallback to live hyprctl monitors if still empty
    if not monitors:
        try:
            res = subprocess.run(
                ["hyprctl", "monitors", "all", "-j"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                raw = json.loads(res.stdout)
                for m in raw:
                    monitors.append({
                        "name": m.get("name", ""),
                        "resolution": f"{m.get('width', 0)}x{m.get('height', 0)}@{m.get('refreshRate', 60):.2f}",
                        "position": f"{m.get('x', 0)}x{m.get('y', 0)}",
                        "scale": str(m.get("scale", 1.0)),
                    })
        except Exception:
            pass

    workspaces.sort(key=lambda w: w["number"])

    ws_options = [("default", t("Standard (no rule)"))]
    for ws in workspaces:
        label = (
            f"WS {ws['number']}  –  {ws['monitor']}"
            if ws["monitor"]
            else f"Workspace {ws['number']}"
        )
        if ws["default"]:
            label += "  ★"
        ws_options.append((str(ws["number"]), label))

    for sp in ["sysmon", "music", "communication", "todo", "scratch"]:
        ws_options.append((f"special:{sp}", f"Special: {sp}"))

    if not ws_options or len(ws_options) <= 6:
        ws_options = _fallback_ws_options()

    return {
        "monitors": monitors,
        "workspaces": workspaces,
        "workspace_options": ws_options,
    }


def _fallback_ws_options() -> list:
    opts = [("default", t("Standard (no rule)"))]
    for i in range(1, 21):
        opts.append((str(i), f"Workspace {i}"))
    for sp in ["sysmon", "music", "communication", "todo", "scratch"]:
        opts.append((f"special:{sp}", f"Special: {sp}"))
    return opts


def parse_rules_conf() -> list:
    """
    Liest rules.conf oder rules.lua und gibt alle windowrule-Einträge strukturiert zurück.
    { "rule": "workspace special:music", "match_type": "class",
      "match_val": "feishin|Spotify", "raw": "...", "managed": False }
    """
    result = []

    # 1. Check Lua mode rules (~/.config/caelestia/rules.lua)
    if is_lua_mode() and CAELESTIA_RULES_LUA.exists():
        try:
            text = CAELESTIA_RULES_LUA.read_text()
            for m in re.finditer(r"hl\.window_rule\s*\((.*?)\)", text, re.DOTALL):
                body = m.group(1)
                match_type = "class"
                match_val = ""
                c_m = re.search(r'class\s*=\s*["\']([^"\']+)["\']', body)
                t_m = re.search(r'(?:initial_title|title)\s*=\s*["\']([^"\']+)["\']', body)
                if c_m:
                    match_type = "class"
                    match_val = c_m.group(1)
                elif t_m:
                    match_type = "initial_title"
                    match_val = t_m.group(1)

                rule_desc = ""
                ws_m = re.search(r'workspace\s*=\s*["\']([^"\']+)["\']', body)
                if ws_m:
                    rule_desc = f"workspace {ws_m.group(1)}"
                if re.search(r'float\s*=\s*true', body, re.IGNORECASE):
                    rule_desc = (rule_desc + " float true").strip()

                result.append({
                    "rule": rule_desc or "windowrule",
                    "match_type": match_type,
                    "match_val": match_val,
                    "raw": m.group(0).strip(),
                    "managed": True,
                })
        except Exception as e:
            print(f"Fehler beim Parsen von rules.lua: {e}")

    # 2. Check rules.conf
    if HYPR_RULES_CONF.exists():
        try:
            for r in caelestia_core.parse_rules_conf(HYPR_RULES_CONF.read_text()):
                result.append({
                    "rule": r.rule,
                    "match_type": r.match_type,
                    "match_val": r.match_val,
                    "raw": r.raw,
                    "managed": r.managed,
                })
        except Exception as e:
            print(f"Fehler beim Parsen von rules.conf: {e}")

    return result