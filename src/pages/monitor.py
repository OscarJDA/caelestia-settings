import json
import subprocess
import cairo
from src.lang import t
from gi.repository import Gtk, Adw, GLib

# ── Konstanten ────────────────────────────────────────────────────────────────

ROTATION_OPTIONS = [
    ("0",   t("Normal (0°)")),
    ("1",   t("90° right")),
    ("2",   "180°"),
    ("3",   t("270° right / 90° left")),
]

BITDEPTH_OPTIONS = [
    ("",   t("Standard (8 bit)")),
    ("8",  "8 bit"),
    ("10", t("10 bit (HDR)")),
]

VRR_OPTIONS = [
    ("0", t("Off")),
    ("1", t("Always on")),
    ("2", t("Fullscreen only")),
    ("3", t("Fullscreen + video")),
]

# Farben für Monitor-Rechtecke (Index → RGBA)
MONITOR_COLORS = [
    (0.27, 0.52, 0.93, 1.0),   # Blau
    (0.20, 0.78, 0.56, 1.0),   # Grün
    (0.93, 0.47, 0.27, 1.0),   # Orange
    (0.73, 0.40, 0.93, 1.0),   # Lila
    (0.93, 0.27, 0.47, 1.0),   # Rot
]

CANVAS_H = 220   # Höhe der Vorschau-Canvas in Pixeln


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _get_live_monitors() -> list[dict]:
    """Liefert die aktuellen Monitor-Daten von hyprctl, angereichert mit
    Extras aus monitors.conf / monitors.lua (bitdepth)."""
    try:
        res = subprocess.run(
            ["hyprctl", "monitors", "all", "-j"],
            capture_output=True, text=True, check=True, timeout=3
        )
        monitors = json.loads(res.stdout)
    except Exception as e:
        print(f"hyprctl fehler: {e}")
        return []

    # Extras aus config lesen (bitdepth, vrr, mirror)
    extras = _parse_conf_extras()
    for m in monitors:
        name = m.get("name", "")
        mirror_of = m.get("mirrorOf")
        if mirror_of and mirror_of != "none":
            m["mirror"] = mirror_of
        if name in extras:
            m.update(extras[name])
    return monitors


def _parse_conf_extras() -> dict:
    """
    Liest monitors.lua oder monitors.conf und extrahiert pro Monitor-Name:
    { "DP-1": {"bitdepth": "10", "vrr": "2", "mirror": "HDMI-A-1"} }
    """
    import re
    from src.config import is_lua_mode, CAELESTIA_MONITORS_LUA, HYPR_MONITORS_CONF

    result = {}

    # 1. Lua mode
    if is_lua_mode() and CAELESTIA_MONITORS_LUA.exists():
        try:
            text = CAELESTIA_MONITORS_LUA.read_text()
            for m in re.finditer(r"hl\.monitor\s*\(\s*\{([^}]+)\}\s*\)", text):
                body = m.group(1)
                name_m = re.search(r'output\s*=\s*["\']([^"\']+)["\']', body)
                if not name_m:
                    continue
                extras = {}
                bd_m = re.search(r'bitdepth\s*=\s*([0-9]+)', body)
                vrr_m = re.search(r'vrr\s*=\s*([0-9]+)', body)
                mirror_m = re.search(r'mirror\s*=\s*["\']([^"\']+)["\']', body)
                if bd_m:
                    extras["bitdepth"] = bd_m.group(1)
                if vrr_m:
                    extras["vrr"] = vrr_m.group(1)
                if mirror_m:
                    extras["mirror"] = mirror_m.group(1)
                result[name_m.group(1)] = extras
        except Exception as e:
            print(f"Fehler beim Lesen von monitors.lua extras: {e}")
        return result

    # 2. Conf mode
    if not HYPR_MONITORS_CONF.exists():
        return result
    try:
        for line in HYPR_MONITORS_CONF.read_text().splitlines():
            line = line.strip()
            if not line.startswith("monitor"):
                continue
            rest = line.split("=", 1)[1]
            tokens = [t.strip() for t in rest.split(",")]
            if len(tokens) < 1:
                continue
            name = tokens[0]
            extras = {}
            for i, tok in enumerate(tokens):
                key = tok.lower()
                if key in ("bitdepth", "vrr", "mirror") and i + 1 < len(tokens):
                    extras[key] = tokens[i + 1].strip()
            result[name] = extras
    except Exception as e:
        print(f"Fehler beim Lesen von monitors.conf extras: {e}")
    return result


def _apply_to_hyprland(monitors: list):
    """Schickt alle Monitor-Konfigurationen live an Hyprland."""
    from src.config import is_lua_mode, hyprctl_eval

    if is_lua_mode():
        for m in monitors:
            if m.disabled:
                hyprctl_eval(f'hl.monitor({{ output = "{m.name}", disabled = true }})')
            else:
                res_hz = f"{m.resolution}@{m.hz}" if m.hz else m.resolution
                pos = f"{int(m.x)}x{int(m.y)}"
                parts = [f'output = "{m.name}"', f'mode = "{res_hz}"', f'position = "{pos}"', f'scale = {m.scale}']
                if m.bitdepth:
                    parts.append(f'bitdepth = {m.bitdepth}')
                if m.transform and m.transform != "0":
                    parts.append(f'transform = {m.transform}')
                if getattr(m, "vrr", "0"):
                    parts.append(f'vrr = {m.vrr}')
                if getattr(m, "mirror", ""):
                    parts.append(f'mirror = "{m.mirror}"')
                hyprctl_eval(f"hl.monitor({{ {', '.join(parts)} }})")
        return

    for m in monitors:
        keyword = _build_monitor_keyword(m)
        try:
            subprocess.run(
                ["hyprctl", "keyword", "monitor", keyword],
                check=True, timeout=3
            )
        except Exception as e:
            print(f"hyprctl keyword fehler: {e}")


def _save_monitors_conf(monitors: list):
    """Schreibt monitors.lua (Lua-Modus) oder monitors.conf — behält workspace-Zeilen bei."""
    from src.config import (
        is_lua_mode,
        ensure_hypr_user_lua,
        hyprctl_reload,
        CAELESTIA_MONITORS_LUA,
        HYPR_MONITORS_CONF,
    )

    if is_lua_mode():
        # Bestehende Workspace-Regeln aus monitors.lua behalten
        ws_lines = []
        if CAELESTIA_MONITORS_LUA.exists():
            for line in CAELESTIA_MONITORS_LUA.read_text().splitlines():
                s = line.strip()
                if "hl.workspace_rule" in s:
                    ws_lines.append(line)

        lines = ["-- Auto-generated by Caelestia Settings – Monitore", ""]
        for m in monitors:
            if m.disabled:
                lines.append(f'hl.monitor({{ output = "{m.name}", disabled = true }})')
            else:
                res_hz = f"{m.resolution}@{m.hz}" if m.hz else m.resolution
                pos = f"{int(m.x)}x{int(m.y)}"
                parts = [f'output = "{m.name}"', f'mode = "{res_hz}"', f'position = "{pos}"', f'scale = {m.scale}']
                if m.bitdepth:
                    parts.append(f'bitdepth = {m.bitdepth}')
                if m.transform and m.transform != "0":
                    parts.append(f'transform = {m.transform}')
                if getattr(m, "vrr", "0"):
                    parts.append(f'vrr = {m.vrr}')
                if getattr(m, "mirror", ""):
                    parts.append(f'mirror = "{m.mirror}"')
                lines.append(f"hl.monitor({{ {', '.join(parts)} }})")

        if ws_lines:
            lines.append("")
            lines.append("-- Workspaces")
            lines.extend(ws_lines)

        CAELESTIA_MONITORS_LUA.parent.mkdir(parents=True, exist_ok=True)
        CAELESTIA_MONITORS_LUA.write_text("\n".join(lines) + "\n")
        ensure_hypr_user_lua()
        hyprctl_reload()
        return

    HYPR_MONITORS_CONF.parent.mkdir(parents=True, exist_ok=True)

    # Bestehende workspace-Zeilen lesen
    ws_lines = []
    if HYPR_MONITORS_CONF.exists():
        for line in HYPR_MONITORS_CONF.read_text().splitlines():
            s = line.strip()
            if s.startswith("workspace") or (s.startswith("#") and ws_lines):
                ws_lines.append(line)

    lines = ["# Auto-generated by Caelestia Settings – Monitore", ""]
    for m in monitors:
        lines.append(f"monitor = {_build_monitor_keyword(m)}")
    if ws_lines:
        lines.append("")
        lines.append("# Workspaces")
        lines.extend(ws_lines)

    HYPR_MONITORS_CONF.write_text("\n".join(lines) + "\n")


# ── Primary Monitor Helpers ──────────────────────────────────────────────────

def _get_primary_monitor() -> str:
    """Liest den aktuellen Hauptmonitor aus hypr-user.lua oder execs.conf."""
    from src.config import is_lua_mode, CAELESTIA_HYPR_USER, HYPR_EXECS_CONF

    if is_lua_mode() and CAELESTIA_HYPR_USER.exists():
        for line in CAELESTIA_HYPR_USER.read_text().splitlines():
            line = line.strip()
            if "xrandr" in line and "--primary" in line:
                parts = line.split()
                try:
                    idx = parts.index("--output")
                    name = parts[idx + 1].strip("'\"")
                    return name
                except (ValueError, IndexError):
                    pass
        return ""

    if not HYPR_EXECS_CONF.exists():
        return ""
    for line in HYPR_EXECS_CONF.read_text().splitlines():
        line = line.strip()
        if "xrandr --output" in line and "--primary" in line:
            parts = line.split()
            try:
                idx = parts.index("--output")
                return parts[idx + 1]
            except (ValueError, IndexError):
                pass
    return ""


def _set_primary_monitor(name: str):
    """Schreibt/ersetzt die xrandr --primary Zeile in hypr-user.lua oder execs.conf."""
    from src.config import is_lua_mode, CAELESTIA_HYPR_USER, HYPR_EXECS_CONF, ensure_hypr_user_lua

    if is_lua_mode():
        ensure_hypr_user_lua()
        new_line = f'hl.exec_cmd("xrandr --output {name} --primary")'
        content = CAELESTIA_HYPR_USER.read_text()
        lines = content.splitlines()
        replaced = False
        for i, line in enumerate(lines):
            if "xrandr" in line and "--primary" in line:
                lines[i] = new_line
                replaced = True
                break
        if not replaced:
            lines.append(new_line)
        CAELESTIA_HYPR_USER.write_text("\n".join(lines) + "\n")
    else:
        HYPR_EXECS_CONF.parent.mkdir(parents=True, exist_ok=True)
        new_line = f"exec-once = xrandr --output {name} --primary"
        if HYPR_EXECS_CONF.exists():
            lines = HYPR_EXECS_CONF.read_text().splitlines()
            replaced = False
            for i, line in enumerate(lines):
                if "xrandr --output" in line and "--primary" in line:
                    lines[i] = new_line
                    replaced = True
                    break
            if not replaced:
                for i, line in enumerate(lines):
                    if "Monitor Settings" in line:
                        lines.insert(i + 1, new_line)
                        replaced = True
                        break
                if not replaced:
                    lines.append(new_line)
            HYPR_EXECS_CONF.write_text("\n".join(lines) + "\n")
        else:
            HYPR_EXECS_CONF.write_text(f"# Monitor Settings\n{new_line}\n")

    # Live anwenden
    try:
        subprocess.run(["xrandr", "--output", name, "--primary"],
                       timeout=3, capture_output=True)
    except Exception as e:
        print(f"xrandr fehler: {e}")


# ── shell.json Helpers ───────────────────────────────────────────────────────

def _get_bar_persistent(monitor_name: str) -> bool:
    """Liest, ob die Taskleiste für diesen Monitor persistent ist.

    Per-monitor shell.json overrides take precedence; otherwise inherit the
    global bar.persistent value from ~/.config/caelestia/shell.json.
    """
    import json
    from pathlib import Path
    from src.config import CAELESTIA_SHELL_JSON

    def _read(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    override = (
        Path.home() / ".config/caelestia/monitors" / monitor_name / "shell.json"
    )
    if override.exists():
        data = _read(override)
        value = data.get("bar", {}).get("persistent")
        if isinstance(value, bool):
            return value
        if isinstance(value, dict):
            print(f"Unexpected bar.persistent override for {monitor_name}: {value!r}")
    return bool(_read(CAELESTIA_SHELL_JSON).get("bar", {}).get("persistent", True))


def _set_bar_persistent(monitor_name: str, persistent: bool):
    """Schreibt den persistent-Wert in shell.json."""
    import json
    from pathlib import Path
    shell_dir = Path.home() / ".config/caelestia/monitors" / monitor_name
    shell_dir.mkdir(parents=True, exist_ok=True)
    shell = shell_dir / "shell.json"
    try:
        data = {}
        if shell.exists():
            data = json.loads(shell.read_text())
        data.setdefault("bar", {})["persistent"] = persistent
        from src.safe_io import atomic_write_json

        atomic_write_json(shell, data)
    except Exception as e:
        print(f"shell.json schreiben fehler: {e}")


def _build_monitor_keyword(m) -> str:
    """
    Baut den Hyprland monitor-Keyword-String aus einem MonitorModel.
    DP-1,2560x1440@179.95,0x0,1,bitdepth,10,transform,3
    """
    if m.disabled:
        return f"{m.name},disable"

    res_hz = f"{m.resolution}@{m.hz}" if m.hz else m.resolution
    pos    = f"{int(m.x)}x{int(m.y)}"
    parts  = [m.name, res_hz, pos, str(m.scale)]

    if m.bitdepth:
        parts += ["bitdepth", m.bitdepth]

    if m.transform and m.transform != "0":
        parts += ["transform", m.transform]

    if getattr(m, "vrr", "0"):
        parts += ["vrr", m.vrr]

    if getattr(m, "mirror", ""):
        parts += ["mirror", m.mirror]

    return ",".join(parts)


def _parse_mode(mode_str: str) -> tuple[str, str]:
    """'2560x1440@179.950Hz' → ('2560x1440', '179.950')"""
    if "@" in mode_str:
        res, hz = mode_str.split("@", 1)
        hz = hz.replace("Hz", "").strip()
        try:
            hz = f"{float(hz):.3f}"   # normalisieren auf 3 Dezimalstellen
        except ValueError:
            pass
        return res, hz
    return mode_str, ""


# ── Monitor-Datenmodell ───────────────────────────────────────────────────────

class MonitorModel:
    """Hält den Zustand eines Monitors (editierbar)."""

    def __init__(self, data: dict):
        self.name        = data["name"]
        self.description = data.get("description", self.name)
        self.x           = float(data.get("x", 0))
        self.y           = float(data.get("y", 0))
        self.width       = int(data.get("width", 1920))
        self.height      = int(data.get("height", 1080))
        self.scale       = float(data.get("scale", 1.0))
        self.transform   = str(int(data.get("transform", 0)))
        self.disabled    = data.get("disabled", False)

        # Aktive Auflösung + Hz
        self.resolution  = f"{self.width}x{self.height}"
        self.hz          = f"{round(data.get('refreshRate', 60), 3):.3f}"

        # Bitdepth aus monitors.conf (via _parse_conf_extras angereichert)
        self.bitdepth    = str(data.get("bitdepth", ""))
        # VRR: raw config value (0-3) if present, otherwise the live boolean
        raw_vrr = data.get("vrr")
        if isinstance(raw_vrr, str):
            self.vrr = raw_vrr
        else:
            self.vrr = "1" if raw_vrr else "0"
        # Mirror target ("" = off)
        self.mirror = str(data.get("mirror") or "")
        if self.mirror == "none":
            self.mirror = ""
        # Hauptmonitor-Flag — wird separat aus execs.conf gesetzt
        self.primary     = False
        # Taskleiste persistent — wird aus shell.json geladen
        self.bar_persistent = True

        # Alle Modi
        self.available_modes: list[str] = data.get("availableModes", [])
        if not self.available_modes:
            self.available_modes = [f"{self.resolution}@{self.hz}Hz"]

        # Deduplizierte Auflösungen + Hz-Optionen pro Auflösung
        self._res_map: dict[str, list[str]] = {}
        for mode in self.available_modes:
            r, h = _parse_mode(mode)
            self._res_map.setdefault(r, []).append(h)

    @property
    def logical_w(self) -> float:
        """Logische Breite. hyprctl liefert bereits getauschte width/height
        bei rotierten Monitoren, also immer width/scale."""
        return self.width / self.scale

    @property
    def logical_h(self) -> float:
        return self.height / self.scale

    def resolutions(self) -> list[str]:
        return sorted(self._res_map.keys(),
                      key=lambda r: int(r.split("x")[0]), reverse=True)

    def hz_for_resolution(self, res: str) -> list[str]:
        return sorted(self._res_map.get(res, []),
                      key=lambda h: float(h) if h else 0, reverse=True)

    def to_save_dict(self) -> dict:
        return {
            "name":       self.name,
            "resolution": self.resolution,
            "hz":         self.hz,
            "x":          self.x,
            "y":          self.y,
            "scale":      self.scale,
            "transform":  self.transform,
            "bitdepth":   self.bitdepth,
            "vrr":        self.vrr,
            "mirror":     self.mirror,
        }


# ── Canvas ────────────────────────────────────────────────────────────────────

class MonitorCanvas(Gtk.DrawingArea):
    """
    Zeichnet alle Monitore als Rechtecke.
    Klick → Monitor auswählen.
    Drag → Monitor verschieben (snap an anderen Monitoren).
    """

    def __init__(self, on_select_cb):
        super().__init__()
        self.on_select_cb = on_select_cb
        self.monitors: list[MonitorModel] = []
        self.selected: MonitorModel | None = None
        self._drag_mon: MonitorModel | None = None
        self._drag_off_x = 0.0
        self._drag_off_y = 0.0

        self.set_vexpand(False)
        self.set_hexpand(True)
        self.set_content_height(CANVAS_H)
        self.set_draw_func(self._draw)

        # Gesten
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_press)
        self.add_controller(click)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin",  self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end",    self._on_drag_end)
        self.add_controller(drag)

    # ── Koordinaten-Umrechnung ────────────────────────────────────────────

    def _canvas_rect(self, m: MonitorModel, scale: float, ox: float, oy: float):
        """Gibt (cx, cy, cw, ch) in Canvas-Pixeln zurück."""
        cw = max(m.logical_w * scale, 40)
        ch = max(m.logical_h * scale, 30)
        cx = ox + m.x * scale
        cy = oy + m.y * scale
        return cx, cy, cw, ch

    def _view_scale_offset(self) -> tuple[float, float, float]:
        """Berechnet Skalierungsfaktor und Offset so dass alle Monitore passen."""
        if not self.monitors:
            return 0.1, 20, 20

        active = [m for m in self.monitors if not m.disabled]
        if not active:
            return 0.1, 20, 20

        min_x = min(m.x for m in active)
        min_y = min(m.y for m in active)
        max_x = max(m.x + m.logical_w for m in active)
        max_y = max(m.y + m.logical_h for m in active)

        w = self.get_width()
        h = self.get_height()
        pad = 32

        sw = (w - 2 * pad) / max(max_x - min_x, 1)
        sh = (h - 2 * pad) / max(max_y - min_y, 1)
        s  = min(sw, sh, 0.18)   # max 0.18 px/logical-px

        ox = pad - min_x * s + (w - 2*pad - (max_x-min_x)*s) / 2
        oy = pad - min_y * s + (h - 2*pad - (max_y-min_y)*s) / 2
        return s, ox, oy

    # ── Zeichnen ──────────────────────────────────────────────────────────

    def _draw(self, area, cr, w, h):
        s, ox, oy = self._view_scale_offset()

        # Hintergrund
        cr.set_source_rgba(0.12, 0.12, 0.12, 1)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Gitter
        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.set_line_width(1)
        step = 40
        for gx in range(0, w, step):
            cr.move_to(gx, 0); cr.line_to(gx, h)
        for gy in range(0, h, step):
            cr.move_to(0, gy); cr.line_to(w, gy)
        cr.stroke()

        for i, m in enumerate(self.monitors):
            if m.disabled:
                continue
            cx, cy, cw, ch = self._canvas_rect(m, s, ox, oy)
            r, g, b, a = MONITOR_COLORS[i % len(MONITOR_COLORS)]
            selected = (m is self.selected)

            # Schatten
            cr.set_source_rgba(0, 0, 0, 0.4)
            cr.rectangle(cx + 4, cy + 4, cw, ch)
            cr.fill()

            # Füllung
            alpha = 1.0 if selected else 0.75
            cr.set_source_rgba(r * 0.6, g * 0.6, b * 0.6, alpha)
            cr.rectangle(cx, cy, cw, ch)
            cr.fill()

            # Rahmen
            lw = 3 if selected else 1.5
            cr.set_line_width(lw)
            cr.set_source_rgba(r, g, b, 1.0)
            cr.rectangle(cx, cy, cw, ch)
            cr.stroke()

            # Name
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD if selected else cairo.FONT_WEIGHT_NORMAL)
            font_size = max(min(cw / 6, 16), 9)
            cr.set_font_size(font_size)
            ext = cr.text_extents(m.name)
            cr.move_to(cx + cw/2 - ext.width/2, cy + ch/2 - 2)
            cr.show_text(m.name)

            # Auflösung
            res_str = f"{m.resolution}@{float(m.hz):.0f}Hz"
            cr.set_font_size(max(font_size * 0.7, 7))
            cr.set_source_rgba(1, 1, 1, 0.7)
            ext2 = cr.text_extents(res_str)
            if ext2.width < cw - 8:
                cr.move_to(cx + cw/2 - ext2.width/2, cy + ch/2 + font_size)
                cr.show_text(res_str)

            # Rotation-Indikator
            if m.transform != "0":
                deg = {"1": "90°", "2": "180°", "3": "270°"}.get(m.transform, "")
                cr.set_font_size(max(font_size * 0.65, 7))
                cr.set_source_rgba(1, 1, 0.4, 0.9)
                cr.move_to(cx + 4, cy + 14)
                cr.show_text(f"↻ {deg}")

    # ── Interaktion ───────────────────────────────────────────────────────

    def _mon_at(self, px, py) -> MonitorModel | None:
        s, ox, oy = self._view_scale_offset()
        for m in reversed(self.monitors):
            if m.disabled: continue
            cx, cy, cw, ch = self._canvas_rect(m, s, ox, oy)
            if cx <= px <= cx+cw and cy <= py <= cy+ch:
                return m
        return None

    def _on_press(self, gesture, n, px, py):
        m = self._mon_at(px, py)
        self.selected = m
        self.queue_draw()
        self.on_select_cb(m)

    def _on_drag_begin(self, gesture, sx, sy):
        self._drag_mon = self._mon_at(sx, sy)
        if self._drag_mon:
            s, ox, oy = self._view_scale_offset()
            self._drag_off_x = (sx - ox) / s - self._drag_mon.x
            self._drag_off_y = (sy - oy) / s - self._drag_mon.y

    def _on_drag_update(self, gesture, dx, dy):
        if not self._drag_mon: return
        sx, sy = gesture.get_start_point()[1], gesture.get_start_point()[2]
        px, py = sx + dx, sy + dy
        s, ox, oy = self._view_scale_offset()
        new_x = (px - ox) / s - self._drag_off_x
        new_y = (py - oy) / s - self._drag_off_y
        self._drag_mon.x = round(new_x)
        self._drag_mon.y = round(new_y)
        self.queue_draw()

    def _on_drag_end(self, gesture, dx, dy):
        if self._drag_mon:
            self._snap(self._drag_mon)
            self.queue_draw()
        self._drag_mon = None

    def _snap(self, m: MonitorModel, threshold: float = 30):
        """Rastet Monitor an benachbarten Monitoren ein."""
        for other in self.monitors:
            if other is m or other.disabled:
                continue
            # Horizontal
            for mx in [m.x, m.x + m.logical_w]:
                for ox_ in [other.x, other.x + other.logical_w]:
                    if abs(mx - ox_) < threshold:
                        m.x += ox_ - mx
            # Vertikal
            for my in [m.y, m.y + m.logical_h]:
                for oy_ in [other.y, other.y + other.logical_h]:
                    if abs(my - oy_) < threshold:
                        m.y += oy_ - my


# ── Einstellungs-Panel ────────────────────────────────────────────────────────

class MonitorSettingsPanel(Gtk.Box):
    """Zeigt Einstellungen für den ausgewählten Monitor."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._monitor: MonitorModel | None = None
        self._loading = False
        self._on_primary_exclusive_cb = None

        self._placeholder = Adw.StatusPage()
        self._placeholder.set_icon_name("video-display-symbolic")
        self._placeholder.set_title(t("No monitor selected"))
        self._placeholder.set_description(t("Click on a monitor in the preview."))
        self._placeholder.set_vexpand(True)
        self.append(self._placeholder)

        self._panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._panel.set_vexpand(True)
        self._panel.set_visible(False)
        self.append(self._panel)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._panel.append(scroller)

        self._group = Adw.PreferencesGroup()
        self._group.set_margin_top(8)
        self._group.set_margin_bottom(12)
        self._group.set_margin_start(12)
        self._group.set_margin_end(12)
        scroller.set_child(self._group)

        # ── Auflösung ──
        res_row = Adw.ActionRow(title=t("Resolution"))
        self._res_combo = Gtk.ComboBoxText()
        self._res_combo.set_valign(Gtk.Align.CENTER)
        self._res_combo.connect("changed", self._on_res_changed)
        res_row.add_suffix(self._res_combo)
        self._group.add(res_row)

        # ── Bildwiederholrate ──
        hz_row = Adw.ActionRow(title=t("Refresh rate"))
        self._hz_combo = Gtk.ComboBoxText()
        self._hz_combo.set_valign(Gtk.Align.CENTER)
        self._hz_combo.connect("changed", self._on_hz_changed)
        hz_row.add_suffix(self._hz_combo)
        self._group.add(hz_row)

        # ── Drehung ──
        rot_row = Adw.ActionRow(title=t("Rotation"))
        self._rot_combo = Gtk.ComboBoxText()
        self._rot_combo.set_valign(Gtk.Align.CENTER)
        for r_id, r_lbl in ROTATION_OPTIONS:
            self._rot_combo.append(r_id, r_lbl)
        self._rot_combo.connect("changed", self._on_rot_changed)
        rot_row.add_suffix(self._rot_combo)
        self._group.add(rot_row)

        # ── Farbtiefe ──
        bd_row = Adw.ActionRow(title=t("Bit depth"))
        self._bd_combo = Gtk.ComboBoxText()
        self._bd_combo.set_valign(Gtk.Align.CENTER)
        for b_id, b_lbl in BITDEPTH_OPTIONS:
            self._bd_combo.append(b_id, b_lbl)
        self._bd_combo.connect("changed", self._on_bd_changed)
        bd_row.add_suffix(self._bd_combo)
        self._group.add(bd_row)

        # ── Variable refresh rate ──
        vrr_row = Adw.ActionRow(
            title=t("Variable refresh rate"),
            subtitle=t("VRR / FreeSync / adaptive sync"),
        )
        self._vrr_combo = Gtk.ComboBoxText()
        self._vrr_combo.set_valign(Gtk.Align.CENTER)
        for v_id, v_lbl in VRR_OPTIONS:
            self._vrr_combo.append(v_id, v_lbl)
        self._vrr_combo.connect("changed", self._on_vrr_changed)
        vrr_row.add_suffix(self._vrr_combo)
        self._group.add(vrr_row)

        # ── Mirror ──
        mirror_row = Adw.ActionRow(
            title=t("Mirror display"),
            subtitle=t("Show the same image as another monitor"),
        )
        self._mirror_combo = Gtk.ComboBoxText()
        self._mirror_combo.set_valign(Gtk.Align.CENTER)
        self._mirror_combo.connect("changed", self._on_mirror_changed)
        mirror_row.add_suffix(self._mirror_combo)
        self._group.add(mirror_row)

        # ── Skalierung ──
        scale_row = Adw.ActionRow(title=t("Scale"))
        self._scale_spin = Gtk.SpinButton.new_with_range(0.25, 4.0, 0.25)
        self._scale_spin.set_digits(2)
        self._scale_spin.set_valign(Gtk.Align.CENTER)
        self._scale_spin.connect("value-changed", self._on_scale_changed)
        scale_row.add_suffix(self._scale_spin)
        self._group.add(scale_row)

        # ── Aktiviert ──
        self._enabled_row = Adw.SwitchRow(title=t("Monitor enabled"))
        self._enabled_row.connect("notify::active", self._on_enabled_changed)
        self._group.add(self._enabled_row)

        # ── Hauptmonitor ──
        self._primary_row = Adw.SwitchRow(
            title=t("Primary monitor"),
            subtitle=t("xrandr --primary (for X11 apps and tray)")
        )
        self._primary_row.connect("notify::active", self._on_primary_changed)
        self._group.add(self._primary_row)

        # ── Taskleiste ──
        self._bar_row = Adw.SwitchRow(
            title=t("Always show taskbar"),
            subtitle="shell.json: bar.persistent"
        )
        self._bar_row.connect("notify::active", self._on_bar_changed)
        self._group.add(self._bar_row)

    def load(self, m: MonitorModel | None):
        self._monitor = m
        self._loading = True

        if m is None:
            self._placeholder.set_visible(True)
            self._panel.set_visible(False)
            self._loading = False
            return

        self._placeholder.set_visible(False)
        self._panel.set_visible(True)
        self._group.set_title(f"{m.name}  –  {m.description}")

        # Auflösungen laden
        self._res_combo.remove_all()
        for r in m.resolutions():
            self._res_combo.append(r, r)
        self._res_combo.set_active_id(m.resolution)

        # Hz laden — normalisiere auf 3 Nachkommastellen für konsistenten Vergleich
        self._reload_hz(m.resolution)
        hz_norm = f"{float(m.hz):.3f}" if m.hz else ""
        if not self._hz_combo.set_active_id(hz_norm):
            # Fallback: ersten Eintrag nehmen
            self._hz_combo.set_active(0)
            first = self._hz_combo.get_active_id()
            if first:
                m.hz = first

        self._rot_combo.set_active_id(m.transform)
        self._bd_combo.set_active_id(m.bitdepth if m.bitdepth else "")
        if not self._vrr_combo.set_active_id(m.vrr):
            self._vrr_combo.set_active_id("0")
        self._rebuild_mirror_options(m)
        self._scale_spin.set_value(m.scale)
        self._enabled_row.set_active(not m.disabled)
        self._primary_row.set_active(m.primary)
        self._bar_row.set_active(m.bar_persistent)

        self._loading = False

    def _reload_hz(self, resolution: str):
        self._hz_combo.remove_all()
        if not self._monitor: return
        for h in self._monitor.hz_for_resolution(resolution):
            # ID immer als 3-Dezimalstellen-String für konsistenten Vergleich
            h_norm = f"{float(h):.3f}"
            self._hz_combo.append(h_norm, f"{float(h):.2f} Hz")

    def _on_res_changed(self, combo):
        if self._loading or not self._monitor: return
        res = combo.get_active_id()
        if not res: return
        self._monitor.resolution = res
        w, h = res.split("x")
        self._monitor.width  = int(w)
        self._monitor.height = int(h)
        self._loading = True
        self._reload_hz(res)
        # Höchste Hz als Default
        hz_list = self._monitor.hz_for_resolution(res)
        if hz_list:
            self._hz_combo.set_active_id(hz_list[0])
            self._monitor.hz = hz_list[0]
        self._loading = False

    def _on_hz_changed(self, combo):
        if self._loading or not self._monitor: return
        hz = combo.get_active_id()
        if hz: self._monitor.hz = hz

    def _on_rot_changed(self, combo):
        if self._loading or not self._monitor: return
        t = combo.get_active_id()
        if t is not None: self._monitor.transform = t

    def _on_bd_changed(self, combo):
        if self._loading or not self._monitor: return
        bd = combo.get_active_id()
        if bd is not None: self._monitor.bitdepth = bd

    def set_mirror_options(self, names: list[str]):
        self._mirror_names = list(names)
        if self._monitor:
            self._rebuild_mirror_options(self._monitor)

    def _rebuild_mirror_options(self, m: MonitorModel):
        names = getattr(self, "_mirror_names", [])
        self._loading = True
        try:
            self._mirror_combo.remove_all()
            self._mirror_combo.append("none", t("None"))
            for name in names:
                if name != m.name:
                    self._mirror_combo.append(name, name)
            if not self._mirror_combo.set_active_id(m.mirror or "none"):
                self._mirror_combo.set_active_id("none")
        finally:
            self._loading = False

    def _on_vrr_changed(self, combo):
        if self._loading or not self._monitor: return
        vrr = combo.get_active_id()
        if vrr is not None:
            self._monitor.vrr = vrr

    def _on_mirror_changed(self, combo):
        if self._loading or not self._monitor: return
        mirror = combo.get_active_id()
        if mirror is not None:
            self._monitor.mirror = "" if mirror == "none" else mirror

    def _on_scale_changed(self, spin):
        if self._loading or not self._monitor: return
        self._monitor.scale = spin.get_value()

    def _on_enabled_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.disabled = not row.get_active()

    def _on_bar_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.bar_persistent = row.get_active()

    def _on_primary_changed(self, row, _):
        if self._loading or not self._monitor: return
        self._monitor.primary = row.get_active()
        # Nur einer kann primär sein → alle anderen auf False
        if row.get_active():
            # Signal wird von MonitorPage via callback propagiert
            if hasattr(self, "_on_primary_exclusive_cb") and self._on_primary_exclusive_cb:
                self._on_primary_exclusive_cb(self._monitor)


# ── Haupt-Seite ───────────────────────────────────────────────────────────────

class MonitorPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)
        self._monitors: list[MonitorModel] = []

        # ── Canvas ──
        canvas_frame = Gtk.Frame()
        canvas_frame.set_margin_top(12)
        canvas_frame.set_margin_start(12)
        canvas_frame.set_margin_end(12)
        self._canvas = MonitorCanvas(self._on_monitor_selected)
        canvas_frame.set_child(self._canvas)
        self.append(canvas_frame)

        # Canvas-Hinweis
        hint = Gtk.Label(label=t("Click to select  •  Drag to move"))
        hint.add_css_class("caption")
        hint.set_margin_top(4)
        hint.set_margin_bottom(8)
        self.append(hint)

        # ── Trennlinie ──
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Einstellungs-Panel ──
        self._settings_panel = MonitorSettingsPanel()
        self._settings_panel._on_primary_exclusive_cb = self._on_primary_exclusive
        self.append(self._settings_panel)

        # ── Buttons ──
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)
        btn_box.set_margin_bottom(12)
        btn_box.set_margin_end(12)

        reload_btn = Gtk.Button(label=t("Reload"))
        reload_btn.connect("clicked", lambda _: self.load_monitors())
        btn_box.append(reload_btn)

        apply_btn = Gtk.Button(label=t("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        btn_box.append(apply_btn)

        self.append(btn_box)

        self.load_monitors()

    def load_monitors(self):
        raw = _get_live_monitors()
        self._monitors = [MonitorModel(m) for m in raw]
        self._settings_panel.set_mirror_options([m.name for m in self._monitors])

        # Hauptmonitor aus execs.conf markieren
        primary_name = _get_primary_monitor()
        for m in self._monitors:
            m.primary = (m.name == primary_name)
            m.bar_persistent = _get_bar_persistent(m.name)

        self._canvas.monitors = self._monitors
        self._canvas.selected = None
        self._canvas.queue_draw()
        self._settings_panel.load(None)

    def _on_monitor_selected(self, m: MonitorModel | None):
        self._settings_panel.load(m)
        self._canvas.queue_draw()

    def _on_primary_exclusive(self, primary_mon: MonitorModel):
        """Stellt sicher dass nur ein Monitor als primär markiert ist."""
        for m in self._monitors:
            if m is not primary_mon:
                m.primary = False

    def _on_apply(self, _btn):
        _apply_to_hyprland(self._monitors)
        _save_monitors_conf(self._monitors)
        # Hauptmonitor speichern
        for m in self._monitors:
            if m.primary:
                _set_primary_monitor(m.name)
            # Taskleiste speichern
            _set_bar_persistent(m.name, m.bar_persistent)
        GLib.timeout_add(600, self.load_monitors)
        self.main_window.add_toast(
            Adw.Toast.new(t("Monitor configuration saved and applied."))
        )

    # Kompatibilität mit window.py (apply_btn dort entfernen wir später)
    def get_all_widget_settings(self):
        return {}