#!/bin/bash
#
# Caelestia Settings — Hyprland integration doctor
#
# Checks (and repairs) the handful of hyprland.conf lines the app depends
# on: the Super+I keybind, the rules.conf/monitors.conf `source` lines, and
# the Polkit auth agent autostart. This is the exact same check-then-append
# logic install.sh's "STEP 6: Configuring Hyprland" already runs on every
# install — pulled out here so it can be re-run standalone (e.g. after a
# manual hyprland.conf edit knocked one of these lines out) without a full
# reinstall or git clone, and so install.sh doesn't have to keep two copies
# of the same checks in sync.
#
# Purely additive/idempotent: a missing line is appended, an existing one
# is left alone. Nothing is ever deleted or rewritten, so there is nothing
# here that needs a backup.

set -e

HYPR_CONFIG_DIR="$HOME/.config/hypr"
HYPR_CONFIG_FILE="$HYPR_CONFIG_DIR/hyprland.conf"
HYPR_INCLUDES_DIR="$HYPR_CONFIG_DIR/hyprland"
RULES_CONFIG_FILE="$HYPR_INCLUDES_DIR/rules.conf"
MONITOR_CONFIG_FILE="$HYPR_INCLUDES_DIR/monitors.conf"
KEYBINDS_CONFIG_FILE="$HYPR_INCLUDES_DIR/keybinds.conf"

HYPR_LUA_FILE="$HYPR_CONFIG_DIR/hyprland.lua"
CAELESTIA_DIR="$HOME/.config/caelestia"
CAELESTIA_HYPR_USER="$CAELESTIA_DIR/hypr-user.lua"
CAELESTIA_MONITORS_LUA="$CAELESTIA_DIR/monitors.lua"
CAELESTIA_RULES_LUA="$CAELESTIA_DIR/rules.lua"
CAELESTIA_KEYBINDS_LUA="$CAELESTIA_DIR/user-keybinds.lua"

# Collects "<status>: <label>" strings for the closing summary. Global
# (not local) on purpose: run_hyprland_doctor() is the only place this is
# read back, but keeping it a plain script-level array is simpler than
# threading a return value through check_and_add()'s call sites.
_DOCTOR_RESULTS=()

is_lua_mode() {
    [[ -f "$HYPR_LUA_FILE" ]] || [[ -f "$CAELESTIA_HYPR_USER" && ! -f "$HYPR_CONFIG_FILE" ]]
}

# Returns 0 if any of the "|"-separated literal NEEDLES is present in FILE.
contains_any() {
    local file="$1"
    local needles="$2"
    local n
    local IFS='|'

    for n in $needles; do
        [[ -n "$n" ]] || continue
        if grep -q -F "$n" "$file" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

# check_and_add_lua NEEDLES CONTENT LABEL [ALSO_CHECK_FILE]
#
# NEEDLES is a "|"-separated list of literal strings — alternate spellings of
# the same line, e.g. wrapped in pcall() or not. The line is appended only
# when none of them is present yet. Matching a single exact spelling is how
# this used to add a duplicate copy of these requires on every run: the
# content written is `pcall(require, "x")`, which never contains the needle
# `require("x")` (note the ", " between them).
check_and_add_lua() {
    local needles="$1"
    local content="$2"
    local label="$3"
    local also_check_file="$4"

    if contains_any "$CAELESTIA_HYPR_USER" "$needles" \
        || { [[ -n "$also_check_file" ]] && contains_any "$also_check_file" "$needles"; }; then
        _DOCTOR_RESULTS+=("OK:    $label")
    else
        echo "    ...Adding: $label"
        printf '%s\n' "$content" >> "$CAELESTIA_HYPR_USER"
        _DOCTOR_RESULTS+=("FIXED: $label (was missing, now added)")
    fi
}

# check_and_add NEEDLE CONTENT LABEL [ALSO_CHECK_FILE]
#
# Appends CONTENT (verbatim, may be multi-line) to $HYPR_CONFIG_FILE unless
# NEEDLE is already found there — or, when ALSO_CHECK_FILE is given, found
# in that file instead (grep -F, literal match — these lines can contain
# characters like '.' that would otherwise be regex metacharacters).
check_and_add() {
    local needle="$1"
    local content="$2"
    local label="$3"
    local also_check_file="$4"

    if grep -q -F "$needle" "$HYPR_CONFIG_FILE" \
        || { [[ -n "$also_check_file" ]] && grep -q -F "$needle" "$also_check_file" 2>/dev/null; }; then
        _DOCTOR_RESULTS+=("OK:    $label")
    else
        echo "    ...Adding: $label"
        printf '%s\n' "$content" >> "$HYPR_CONFIG_FILE"
        _DOCTOR_RESULTS+=("FIXED: $label (was missing, now added)")
    fi
}

run_hyprland_doctor() {
    echo ">>> Checking Hyprland integration..."
    _DOCTOR_RESULTS=()

    if is_lua_mode; then
        echo "    ...Detected Caelestia 2.5.0+ (Hyprland Lua configuration mode)"
        mkdir -p "$CAELESTIA_DIR"
        touch "$CAELESTIA_HYPR_USER"
        touch "$CAELESTIA_MONITORS_LUA"
        touch "$CAELESTIA_RULES_LUA"
        touch "$CAELESTIA_KEYBINDS_LUA"

        check_and_add_lua 'pcall(require, "monitors")|require("monitors")' 'pcall(require, "monitors")' "monitors.lua module require"
        check_and_add_lua 'pcall(require, "rules")|require("rules")' 'pcall(require, "rules")' "rules.lua module require"
        check_and_add_lua 'pcall(require, "user-keybinds")|require("user-keybinds")' 'pcall(require, "user-keybinds")' "user-keybinds.lua module require"
        check_and_add_lua 'caelestia-settings' 'hl.bind("SUPER + I", hl.dsp.exec_cmd("caelestia-settings"))' "Super+I keybind" "$CAELESTIA_KEYBINDS_LUA"
        check_and_add_lua 'org.caelestia.settings' 'hl.window_rule({ match = { class = "org.caelestia.settings" }, float = true, center = true })' "Settings window rule (float & center)" "$CAELESTIA_RULES_LUA"

        local polkit_bin="/usr/lib/polkit-kde-authentication-agent-1"
        check_and_add_lua "$polkit_bin" "hl.exec_cmd(\"$polkit_bin\")" "Polkit auth agent autostart"
    else
        echo "    ...Detected classic Hyprland configuration (.conf mode)"
        mkdir -p "$HYPR_CONFIG_DIR"
        mkdir -p "$HYPR_INCLUDES_DIR"
        touch "$HYPR_CONFIG_FILE"
        touch "$RULES_CONFIG_FILE"
        touch "$MONITOR_CONFIG_FILE"

        local rules_source="source = $RULES_CONFIG_FILE"
        check_and_add "$rules_source" "$rules_source" "rules.conf 'source' line"

        local monitor_source="source = $MONITOR_CONFIG_FILE"
        local monitor_block
        monitor_block=$(printf '\n# Caelestia Monitor Config\n%s' "$monitor_source")
        check_and_add "$monitor_source" "$monitor_block" "monitors.conf 'source' line"

        local bind_needle="exec, caelestia-settings"
        local bind_cmd="bind = SUPER, I, exec, caelestia-settings"
        check_and_add "$bind_needle" "$bind_cmd" "Super+I keybind" "$KEYBINDS_CONFIG_FILE"

        local polkit_needle="/usr/lib/polkit-kde-authentication-agent-1"
        local polkit_cmd="exec-once = $polkit_needle"
        check_and_add "$polkit_needle" "$polkit_cmd" "Polkit auth agent autostart"
    fi

    echo
    echo ">>> Hyprland integration summary:"
    for result in "${_DOCTOR_RESULTS[@]}"; do
        echo "   $result"
    done
    echo
}

# Sourced by install.sh (which then calls run_hyprland_doctor itself), but
# also directly runnable on its own: `./doctor.sh` repairs a live config
# without going through install.sh or app_update.sh at all.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_hyprland_doctor
fi
