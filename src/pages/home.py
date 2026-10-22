from pathlib import Path
import shutil
import time

from gi.repository import Adw, GdkPixbuf, GLib, Gtk

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

from src.config import parse_monitors_conf
from src.lang import t
from src.pages.fans import read_cpu_temp, read_gpu_stats
from src.pages.general import KEYBOARD_LAYOUTS, _layout_label, read_input_conf
from src.pages.wallpaper import get_current_wallpaper
from src.pages.wifi import get_active_wifi_connection, has_wifi_adapter

_THUMB_WIDTH = 96
_THUMB_HEIGHT = 54

# (stack name, icon, title, subtitle) — stack names must match src/window.py.
_QUICK_ACTIONS = [
    ("wall", "preferences-desktop-wallpaper-symbolic",
     "Wallpaper", "Change wallpaper and color scheme"),
    ("mon", "video-display-symbolic",
     "Monitor", "Arrange displays and resolutions"),
    ("appearance", "applications-graphics-symbolic",
     "Appearance", "Transparency, scaling and fonts"),
    ("bar", "preferences-desktop-panel-symbolic",
     "Bar", "Configure the shell bar"),
    ("wifi", "network-wireless-symbolic",
     "WLAN", "Scan and connect to networks"),
    ("bluetooth", "bluetooth-symbolic",
     "Bluetooth", "Pair and connect devices"),
    ("keys", "preferences-desktop-keyboard-symbolic",
     "Keybinds", "View and edit shortcuts"),
    ("diag", "dialog-warning-symbolic",
     "Diagnostics", "Validate your configuration"),
    ("upd", "software-update-available-symbolic",
     "Updates", "Check for system updates"),
]


def _layout_display_name(code: str) -> str:
    labels = dict(KEYBOARD_LAYOUTS)
    parts = [part.strip() for part in code.split(",") if part.strip()]
    if parts and all(part in labels for part in parts):
        names = ", ".join(_layout_label(labels[part]) for part in parts)
        return f"{names}  ({code})"
    return code


def _load_thumbnail(path: Path) -> GdkPixbuf.Pixbuf | None:
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(path), _THUMB_WIDTH, _THUMB_HEIGHT, True
        )
    except Exception:
        # Video wallpapers and unreadable files land here; the caller hides
        # the preview instead of showing a broken image.
        return None


class HomePage(Gtk.Box):
    def __init__(self, win, **kwargs):
        super().__init__(**kwargs)
        self.main_window = win
        self.set_orientation(Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        self.append(scroll)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        scroll.set_child(box)

        box.append(self._build_header())
        box.append(self._build_status_group())
        box.append(self._build_quick_actions())

        self.refresh()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label(label=t("Caelestia Settings"))
        title.add_css_class("title-1")
        header.append(title)

        version = Gtk.Label(
            label=f"{t('Version')} {self.main_window.about_page.local_version}"
        )
        version.add_css_class("dim-label")
        header.append(version)

        return header

    def _build_status_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title=t("System at a Glance"))

        refresh_btn = Gtk.Button(label=t("Refresh"))
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.connect("clicked", lambda _btn: self.refresh())
        group.set_header_suffix(refresh_btn)

        self._wallpaper_row = Adw.ActionRow(title=t("Wallpaper"))
        self._wallpaper_thumb = Gtk.Picture()
        self._wallpaper_thumb.set_size_request(_THUMB_WIDTH, _THUMB_HEIGHT)
        self._wallpaper_thumb.set_valign(Gtk.Align.CENTER)
        self._wallpaper_row.add_prefix(self._wallpaper_thumb)
        group.add(self._wallpaper_row)

        self._monitor_row = Adw.ActionRow(title=t("Monitors"))
        group.add(self._monitor_row)

        self._wifi_row = Adw.ActionRow(title=t("WLAN"))
        group.add(self._wifi_row)

        self._layout_row = Adw.ActionRow(title=t("Keyboard Layout"))
        group.add(self._layout_row)

        self._cpu_row = Adw.ActionRow(title=t("CPU Temperature"))
        group.add(self._cpu_row)

        self._gpu_row = Adw.ActionRow(title=t("GPU Temperature"))
        group.add(self._gpu_row)

        self._uptime_row = Adw.ActionRow(title=t("Uptime"))
        group.add(self._uptime_row)

        self._memory_row = Adw.ActionRow(title=t("Memory"))
        group.add(self._memory_row)

        self._storage_row = Adw.ActionRow(title=t("Storage"))
        group.add(self._storage_row)

        return group

    def _build_quick_actions(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title=t("Quick Actions"))

        for page_name, icon, title, subtitle in _QUICK_ACTIONS:
            row = Adw.ActionRow(title=t(title), subtitle=t(subtitle))
            row.add_prefix(Gtk.Image.new_from_icon_name(icon))
            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
            row.set_activatable(True)
            row.connect("activated", self._on_nav_activated, page_name)
            group.add(row)

        return group

    def _on_nav_activated(self, _row, page_name: str):
        self.main_window.navigate(page_name)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self):
        self._refresh_wallpaper()
        self._refresh_monitors()
        self._refresh_wifi()
        self._refresh_layout()
        self._refresh_temperatures()
        self._refresh_system()

    def _refresh_system(self):
        try:
            uptime = int(time.time() - _psutil.boot_time()) if _psutil else 0
            days, rest = divmod(uptime, 86400)
            hours, rest = divmod(rest, 3600)
            minutes = rest // 60
            self._uptime_row.set_subtitle(
                f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
            )
        except Exception:
            self._uptime_row.set_subtitle(t("Not available"))

        if not _psutil:
            self._memory_row.set_subtitle(t("Not available"))
            self._storage_row.set_subtitle(t("Not available"))
            return
        try:
            memory = _psutil.virtual_memory()
            used = memory.used / (1024 ** 3)
            total = memory.total / (1024 ** 3)
            self._memory_row.set_subtitle(f"{used:.1f} / {total:.1f} GiB ({memory.percent:.0f}%)")
        except Exception:
            self._memory_row.set_subtitle(t("Not available"))
        try:
            usage = shutil.disk_usage(Path.home())
            used = usage.used / (1024 ** 3)
            total = usage.total / (1024 ** 3)
            self._storage_row.set_subtitle(f"{used:.0f} / {total:.0f} GiB")
        except Exception:
            self._storage_row.set_subtitle(t("Not available"))

    def _refresh_wallpaper(self):
        current = get_current_wallpaper()
        if not current:
            self._wallpaper_thumb.set_visible(False)
            self._wallpaper_row.set_subtitle(t("Not available"))
            return

        path = Path(current)
        self._wallpaper_row.set_subtitle(GLib.markup_escape_text(path.name))

        pixbuf = _load_thumbnail(path)
        self._wallpaper_thumb.set_pixbuf(pixbuf)
        self._wallpaper_thumb.set_visible(pixbuf is not None)

    def _refresh_monitors(self):
        monitors = parse_monitors_conf()["monitors"]
        if not monitors:
            self._monitor_row.set_subtitle(t("No monitors configured"))
            return

        summary = "  |  ".join(
            f"{m['name']} · {m['resolution']}" if m["resolution"] else m["name"]
            for m in monitors
        )
        self._monitor_row.set_subtitle(GLib.markup_escape_text(summary))

    def _refresh_wifi(self):
        if not has_wifi_adapter():
            self._wifi_row.set_subtitle(t("No Wi-Fi adapter found."))
            return

        ssid = get_active_wifi_connection()
        self._wifi_row.set_subtitle(
            GLib.markup_escape_text(ssid) if ssid else t("Not connected")
        )

    def _refresh_layout(self):
        layout = read_input_conf().get("kb_layout", "").lower()
        self._layout_row.set_subtitle(
            _layout_display_name(layout) if layout else t("Not available")
        )

    def _refresh_temperatures(self):
        cpu = read_cpu_temp()
        self._cpu_row.set_subtitle(f"{cpu} °C" if cpu is not None else t("Not available"))

        gpu = read_gpu_stats()
        if gpu is None:
            self._gpu_row.set_subtitle(t("No supported GPU detected"))
            return

        parts = [f"{gpu['temp']} °C"]
        if gpu["fan_pct"] is not None:
            parts.append(f"{t('Fan')}: {gpu['fan_pct']} %")
        self._gpu_row.set_subtitle("  |  ".join(parts))
