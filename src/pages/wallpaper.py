import json
import os
import shlex
import subprocess
import threading
from pathlib import Path
from src.lang import t
from gi.repository import Gtk, Adw, GLib, GdkPixbuf

from src.config import is_lua_mode, CAELESTIA_HYPR_USER, CAELESTIA_SHELL_JSON
from src.safe_io import atomic_write_json, atomic_write_text, read_json

_SHELL_JSON = CAELESTIA_SHELL_JSON
_EXTRA_SETTINGS = Path.home() / ".config" / "caelestia-settings" / "wallpaper.json"
_DEFAULT_IMAGE_DIR = Path.home() / "Pictures" / "Wallpapers"
VIDEO_DIR = Path.home() / "Videos" / "Wallpaper"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}

THUMB_SIZE    = 160
THUMB_CACHE   = Path.home() / ".cache" / "caelestia-settings" / "thumbs"
_MPV_PID_FILE = Path.home() / ".cache" / "caelestia-settings" / "mpvpaper.pid"
_EXECS_CONF   = Path.home() / ".config" / "hypr" / "hyprland" / "execs.conf"
_MPVPAPER_MARKER = "# caelestia-settings: video-wallpaper"
_MPVPAPER_LUA_MARKER = "-- caelestia-settings: video-wallpaper"


def _get_image_dir() -> Path:
    """Liest wallpaperDir aus ~/.config/caelestia/shell.json mit Fallbacks."""
    try:
        if _SHELL_JSON.exists():
            data = json.loads(_SHELL_JSON.read_text())
            wall_dir = data.get("paths", {}).get("wallpaperDir", "")
            if wall_dir:
                return Path(os.path.expanduser(wall_dir))
    except Exception as e:
        print(f"shell.json lesen fehler: {e}")

    xdg_pictures = os.environ.get("XDG_PICTURES_DIR")
    if xdg_pictures:
        p = Path(os.path.expanduser(xdg_pictures)) / "Wallpapers"
        if p.exists():
            return p

    default_en = Path.home() / "Pictures" / "Wallpapers"
    if default_en.exists():
        return default_en

    default_de = Path.home() / "Bilder" / "Wallpapers"
    if default_de.exists():
        return default_de

    return default_en


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_dirs():
    _get_image_dir().mkdir(parents=True, exist_ok=True)
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_CACHE.mkdir(parents=True, exist_ok=True)


def _write_mpvpaper_autostart(video_path: Path | None):
    if is_lua_mode():
        CAELESTIA_HYPR_USER.parent.mkdir(parents=True, exist_ok=True)
        lines = CAELESTIA_HYPR_USER.read_text().splitlines() if CAELESTIA_HYPR_USER.exists() else []
        lines = [line for line in lines if _MPVPAPER_LUA_MARKER not in line and "mpvpaper" not in line]
        if video_path is not None:
            cmd = f"mpvpaper '*' {shlex.quote(str(video_path))} -o 'loop --no-audio --panscan=1.0'"
            lines.append(f'hl.exec_cmd({json.dumps(cmd)})  {_MPVPAPER_LUA_MARKER}')
        atomic_write_text(CAELESTIA_HYPR_USER, "\n".join(lines) + "\n")
    else:
        _EXECS_CONF.parent.mkdir(parents=True, exist_ok=True)
        lines = _EXECS_CONF.read_text().splitlines() if _EXECS_CONF.exists() else []
        lines = [line for line in lines if _MPVPAPER_MARKER not in line]
        if video_path is not None:
            lines.append(
                f"exec-once = mpvpaper '*' {shlex.quote(str(video_path))}"
                f" -o 'loop --no-audio --panscan=1.0'  {_MPVPAPER_MARKER}"
            )
        atomic_write_text(_EXECS_CONF, "\n".join(lines) + "\n")


def get_current_wallpaper() -> str:
    p = Path.home() / ".local" / "state" / "caelestia" / "wallpaper" / "path.txt"
    try:
        return p.read_text().strip() if p.exists() else ""
    except Exception:
        return ""


def _get_current_scheme_mode() -> str:
    p = Path.home() / ".local" / "state" / "caelestia" / "scheme.json"
    try:
        return json.loads(p.read_text()).get("mode", "dark") if p.exists() else "dark"
    except Exception:
        return "dark"


def _scan(directory: Path, extensions: set) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [f for f in directory.iterdir() if f.is_file() and f.suffix.lower() in extensions],
        key=lambda p: p.name.lower()
    )


def _thumb_path(path: Path) -> Path:
    return THUMB_CACHE / f"{path.stem}_{path.stat().st_size}.jpg"


def _make_image_thumb(path: Path) -> GdkPixbuf.Pixbuf | None:
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), THUMB_SIZE, THUMB_SIZE, True)
    except Exception as e:
        print(f"Thumbnail fehler {path.name}: {e}")
        return None


def _make_video_thumb(path: Path) -> GdkPixbuf.Pixbuf | None:
    cache = _thumb_path(path)
    if not cache.exists():
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(path),
                "-ss", "00:00:02", "-vframes", "1",
                "-vf", f"scale={THUMB_SIZE * 2}:-1",
                str(cache)
            ], capture_output=True, timeout=15)
        except Exception as e:
            print(f"ffmpeg fehler {path.name}: {e}")
            return None
    if cache.exists():
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(cache), THUMB_SIZE, THUMB_SIZE, True)
        except Exception:
            pass
    return None


# ── Desktop Clock Helpers ────────────────────────────────────────────────────

_SHELL_CONFIG = Path.home() / ".config" / "caelestia" / "shell.json"

def _read_shell_json() -> dict:
    try:
        if CAELESTIA_SHELL_JSON.exists():
            return json.loads(CAELESTIA_SHELL_JSON.read_text())
    except Exception as e:
        print(f"shell.json lesen: {e}")
    return {}

def _write_shell_json(data: dict):
    try:
        atomic_write_json(CAELESTIA_SHELL_JSON, data)
    except Exception as e:
        print(f"shell.json schreiben: {e}")

def _get_clock_settings() -> dict:
    data = _read_shell_json()
    return data.get("background", {}).get("desktopClock", {
        "enabled": False,
        "position": "bottom-right",
        "scale": 1.0,
        "invertColors": False,
    })

def _save_clock_settings(settings: dict):
    data = _read_shell_json()
    data.setdefault("background", {})["desktopClock"] = settings
    _write_shell_json(data)


CLOCK_POSITIONS = [
    ("top-left",      t("Top left")),
    ("top-center",    t("Top center")),
    ("top-right",     t("Top right")),
    ("middle-left",   t("Middle left")),
    ("middle-center", t("Middle center")),
    ("middle-right",  t("Middle right")),
    ("bottom-left",   t("Bottom left")),
    ("bottom-center", t("Bottom center")),
    ("bottom-right",  t("Bottom right")),
]


# ── Shared Grid ───────────────────────────────────────────────────────────────

class MediaGrid(Gtk.Box):
    def __init__(self, on_select_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_select = on_select_cb

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self.flow = Gtk.FlowBox()
        self.flow.set_valign(Gtk.Align.START)
        self.flow.set_max_children_per_line(20)
        self.flow.set_min_children_per_line(2)
        self.flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flow.set_row_spacing(8)
        self.flow.set_column_spacing(8)
        self.flow.set_margin_top(8)
        self.flow.set_margin_bottom(12)
        self.flow.set_margin_start(12)
        self.flow.set_margin_end(12)
        self.flow.connect("child-activated", self._on_activated)
        scroller.set_child(self.flow)

        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_size_request(-1, 48)
        self.append(self.spinner)

        self.empty_label = Gtk.Label()
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(32)
        self.empty_label.set_halign(Gtk.Align.CENTER)
        self.empty_label.set_visible(False)
        self.append(self.empty_label)

    def load(self, files: list[Path], current: str, thumb_fn, is_video: bool = False):
        while child := self.flow.get_first_child():
            self.flow.remove(child)
        self.empty_label.set_visible(False)
        self.spinner.set_visible(True)
        self.spinner.start()

        def _thread():
            GLib.idle_add(self._populate, files, current, thumb_fn, is_video)

        threading.Thread(target=_thread, daemon=True).start()

    def _populate(self, files, current, thumb_fn, is_video):
        self.spinner.stop()
        self.spinner.set_visible(False)

        if not files:
            self.empty_label.set_label(
                t("No videos found.\nPlace videos in ~/Videos/Wallpaper/")
                if is_video else
                t("No images found.\nPlace images in the wallpaper folder.")
            )
            self.empty_label.set_visible(True)
            return

        for path in files:
            card = MediaCard(path, current, is_video)
            self.flow.append(card)

        threading.Thread(
            target=self._load_thumbs, args=(files, thumb_fn), daemon=True
        ).start()

    def _load_thumbs(self, files, thumb_fn):
        child = self.flow.get_first_child()
        for path in files:
            if child is None:
                break
            card = child.get_child()
            if isinstance(card, MediaCard):
                pixbuf = thumb_fn(path)
                if pixbuf:
                    GLib.idle_add(card.set_thumbnail, pixbuf)
            child = child.get_next_sibling()

    def _on_activated(self, _, child):
        card = child.get_child()
        if isinstance(card, MediaCard):
            self._on_select(card.path)

    def mark_current(self, path: str):
        child = self.flow.get_first_child()
        while child:
            card = child.get_child()
            if isinstance(card, MediaCard):
                if str(card.path) == path:
                    card.add_css_class("suggested-action")
                else:
                    card.remove_css_class("suggested-action")
            child = child.get_next_sibling()


# ── Media-Karte ───────────────────────────────────────────────────────────────

class MediaCard(Gtk.Box):
    def __init__(self, path: Path, current: str, is_video: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.path = path
        self.set_size_request(THUMB_SIZE, THUMB_SIZE + 30)

        is_current = (str(path) == current)

        self.image = Gtk.Image()
        self.image.set_pixel_size(THUMB_SIZE)
        self.image.set_from_icon_name(
            "video-x-generic-symbolic" if is_video else "image-x-generic-symbolic"
        )
        self.image.set_size_request(THUMB_SIZE, THUMB_SIZE)
        self.image.add_css_class("card")

        if is_current:
            overlay = Gtk.Overlay()
            overlay.set_child(self.image)
            check = Gtk.Image.new_from_icon_name("object-select-symbolic")
            check.set_halign(Gtk.Align.END)
            check.set_valign(Gtk.Align.END)
            check.set_margin_end(4)
            check.set_margin_bottom(4)
            overlay.add_overlay(check)
            self.append(overlay)
            self.add_css_class("suggested-action")
        else:
            self.append(self.image)

        if is_video:
            badge = Gtk.Label(label=t("▶ Video"))
            badge.add_css_class("caption")
            badge.add_css_class("accent")
            self.append(badge)

        stem = path.stem
        name_label = Gtk.Label(label=stem[:22] + ("…" if len(stem) > 22 else ""))
        name_label.add_css_class("caption")
        name_label.set_ellipsize(3)
        self.append(name_label)

    def set_thumbnail(self, pixbuf: GdkPixbuf.Pixbuf):
        self.image.set_from_pixbuf(pixbuf)


# ── Haupt-Seite ───────────────────────────────────────────────────────────────

class WallpaperPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(0)

        _ensure_dirs()

        self._current     = get_current_wallpaper()
        self._scheme_mode = _get_current_scheme_mode()
        self._mpv_proc: subprocess.Popen | None = None
        self._extra = read_json(_EXTRA_SETTINGS, {})
        self._favorites = {str(path) for path in self._extra.get("favorites", [])}
        self._slideshow_source = 0

        # ── Toolbar ──────────────────────────────────────────────────────
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_margin_top(10)
        bar.set_margin_bottom(6)
        bar.set_margin_start(12)
        bar.set_margin_end(12)

        # Tab-Buttons (linked)
        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_box.add_css_class("linked")

        self._tab_img = Gtk.ToggleButton(label=t("🖼 Images"))
        self._tab_img.set_active(True)
        self._tab_img.connect("toggled", self._on_tab_toggle)
        tab_box.append(self._tab_img)

        self._tab_vid = Gtk.ToggleButton(label=t("🎬 Videos"))
        self._tab_vid.set_group(self._tab_img)
        self._tab_vid.connect("toggled", self._on_tab_toggle)
        tab_box.append(self._tab_vid)

        bar.append(tab_box)

        self._random_btn = Gtk.Button(label=t("🔀 Random"))
        self._random_btn.set_tooltip_text(t("Random image from the wallpaper folder"))
        self._random_btn.connect("clicked", self._on_random)
        bar.append(self._random_btn)

        self._fav_btn = Gtk.ToggleButton()
        self._fav_btn.set_icon_name("non-starred-symbolic")
        self._fav_btn.set_tooltip_text(t("Favorite current wallpaper"))
        self._fav_btn.connect("clicked", self._on_favorite_toggled)
        bar.append(self._fav_btn)

        self._fav_filter = Gtk.ToggleButton(label=t("Favorites"))
        self._fav_filter.set_tooltip_text(t("Show favorites only"))
        self._fav_filter.connect("toggled", lambda _b: self._reload())
        bar.append(self._fav_filter)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)

        # Light/Dark
        self._mode_btn = Gtk.ToggleButton()
        self._mode_btn.set_tooltip_text(t("Light / Dark Mode"))
        self._mode_btn.set_active(self._scheme_mode == "light")
        self._mode_btn.set_icon_name(
            "weather-clear-symbolic" if self._scheme_mode == "light"
            else "weather-clear-night-symbolic"
        )
        self._mode_btn.connect("toggled", self._on_mode_toggled)
        bar.append(self._mode_btn)

        reload_btn = Gtk.Button()
        reload_btn.set_icon_name("view-refresh-symbolic")
        reload_btn.set_tooltip_text(t("Reload"))
        reload_btn.connect("clicked", lambda _: self._reload())
        bar.append(reload_btn)

        self.append(bar)

        # ── Pfad-Label ───────────────────────────────────────────────────
        self._path_label = Gtk.Label()
        self._path_label.set_markup(
            f"<small><tt>{str(_get_image_dir()).replace(str(Path.home()), '~')}</tt></small>"
        )
        self._path_label.add_css_class("dim-label")
        self._path_label.set_halign(Gtk.Align.CENTER)
        self._path_label.set_margin_bottom(4)
        self.append(self._path_label)

        # ── Desktop-Uhr Einstellungen (Expander) ─────────────────────────
        clock_expander = Adw.ExpanderRow()
        clock_expander.set_title(t("Desktop clock"))
        clock_expander.set_subtitle(t("Position, size and visibility"))

        # Wrapper da ExpanderRow kein direktes Widget-Child akzeptiert
        clock_box = Gtk.ListBox()
        clock_box.set_selection_mode(Gtk.SelectionMode.NONE)
        clock_box.add_css_class("boxed-list")
        clock_box.set_margin_start(12)
        clock_box.set_margin_end(12)
        clock_box.set_margin_bottom(6)

        clk = _get_clock_settings()

        # An/Aus
        self._clock_enabled = Adw.SwitchRow(title=t("Show clock"))
        self._clock_enabled.set_active(clk.get("enabled", False))
        self._clock_enabled.connect("notify::active", self._on_clock_changed)
        clock_expander.add_row(self._clock_enabled)

        # Position
        pos_row = Adw.ActionRow(title=t("Position"))
        self._clock_pos = Gtk.ComboBoxText()
        self._clock_pos.set_valign(Gtk.Align.CENTER)
        for pid, plabel in CLOCK_POSITIONS:
            self._clock_pos.append(pid, plabel)
        self._clock_pos.set_active_id(clk.get("position", "bottom-right"))
        self._clock_pos.connect("changed", self._on_clock_changed)
        pos_row.add_suffix(self._clock_pos)
        clock_expander.add_row(pos_row)

        # Größe
        scale_row = Adw.ActionRow(title=t("Size"))
        scale_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        scale_box.set_valign(Gtk.Align.CENTER)
        self._clock_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 3.0, 0.1)
        self._clock_scale.set_value(clk.get("scale", 1.0))
        self._clock_scale.set_draw_value(True)
        self._clock_scale.set_size_request(160, -1)
        self._clock_scale.connect("value-changed", self._on_clock_changed)
        scale_box.append(self._clock_scale)
        scale_row.add_suffix(scale_box)
        clock_expander.add_row(scale_row)

        # Farben invertieren
        self._clock_invert = Adw.SwitchRow(title=t("Invert colors"))
        self._clock_invert.set_active(clk.get("invertColors", False))
        self._clock_invert.connect("notify::active", self._on_clock_changed)
        clock_expander.add_row(self._clock_invert)

        clock_box.append(clock_expander)
        self.append(clock_box)

        # ── Wallpaper rotation ────────────────────────────────────────────
        slideshow = Adw.PreferencesGroup(title=t("Wallpaper rotation"))
        slideshow.set_margin_start(12)
        slideshow.set_margin_end(12)
        slideshow.set_margin_bottom(6)
        self._slideshow_enabled = Adw.SwitchRow(
            title=t("Rotate wallpaper"),
            subtitle=t("Switch to a random wallpaper on a timer"),
        )
        self._slideshow_enabled.set_active(bool(self._extra.get("slideshowEnabled", False)))
        self._slideshow_enabled.connect("notify::active", self._on_slideshow_changed)
        slideshow.add(self._slideshow_enabled)

        self._slideshow_interval = Adw.SpinRow.new_with_range(1, 1440, 1)
        self._slideshow_interval.set_title(t("Interval"))
        self._slideshow_interval.set_subtitle(t("Minutes"))
        self._slideshow_interval.set_value(float(self._extra.get("slideshowMinutes", 30)))
        self._slideshow_interval.connect("notify::value", self._on_slideshow_changed)
        slideshow.add(self._slideshow_interval)

        next_row = Adw.ActionRow(title=t("Next wallpaper now"))
        next_btn = Gtk.Button(label=t("Next"))
        next_btn.set_valign(Gtk.Align.CENTER)
        next_btn.connect("clicked", lambda _b: self._slideshow_tick())
        next_row.add_suffix(next_btn)
        slideshow.add(next_row)
        self.append(slideshow)
        self._reschedule_slideshow()
        self._refresh_favorite_button()

        # ── Banner ───────────────────────────────────────────────────────
        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        self.append(self.banner)

        # ── Stack ─────────────────────────────────────────────────────────
        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.append(self._stack)

        self._img_grid = MediaGrid(self._on_image_selected)
        self._vid_grid = MediaGrid(self._on_video_selected)
        self._stack.add_named(self._img_grid, "images")
        self._stack.add_named(self._vid_grid, "videos")

        self._load_images()

    # ── Tab-Wechsel ───────────────────────────────────────────────────────

    def _on_tab_toggle(self, btn):
        if not btn.get_active():
            return
        if btn is self._tab_img:
            self._stack.set_visible_child_name("images")
            self._random_btn.set_sensitive(True)
            self._path_label.set_markup(
                f"<small><tt>{str(_get_image_dir()).replace(str(Path.home()), '~')}</tt></small>"
            )
        else:
            self._stack.set_visible_child_name("videos")
            self._random_btn.set_sensitive(False)
            self._path_label.set_markup(
                f"<small><tt>{str(VIDEO_DIR).replace(str(Path.home()), '~')}</tt></small>"
            )
            # Lazy-load beim ersten Wechsel
            if self._vid_grid.flow.get_first_child() is None \
               and not self._vid_grid.spinner.get_spinning():
                self._load_videos()

    def _reload(self):
        if self._stack.get_visible_child_name() == "images":
            self._load_images()
        else:
            self._load_videos()

    # ── Laden ─────────────────────────────────────────────────────────────

    def _load_images(self):
        files = _scan(_get_image_dir(), IMAGE_EXTENSIONS)
        if self._fav_filter.get_active():
            files = [path for path in files if str(path) in self._favorites]
        self._img_grid.load(files, self._current, _make_image_thumb, is_video=False)

    def _load_videos(self):
        files = _scan(VIDEO_DIR, VIDEO_EXTENSIONS)
        if self._fav_filter.get_active():
            files = [path for path in files if str(path) in self._favorites]
        self._vid_grid.load(files, self._current, _make_video_thumb, is_video=True)

    # ── Auswahl ───────────────────────────────────────────────────────────

    def _on_image_selected(self, path: Path):
        self._stop_mpv()
        try:
            subprocess.Popen(["caelestia", "wallpaper", "-f", str(path)])
            _write_mpvpaper_autostart(None)
            self._current = str(path)
            self._img_grid.mark_current(self._current)
            self._refresh_favorite_button()
            self._show_banner(t("Wallpaper: {name}").format(name=path.name))
            self.main_window.add_toast(Adw.Toast.new(t("Wallpaper: {name}").format(name=path.name)))
        except Exception as e:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

    def _on_video_selected(self, path: Path):
        self._stop_mpv()
        try:
            self._mpv_proc = subprocess.Popen([
                "mpvpaper", "*", str(path),
                "-o", "loop --no-audio --panscan=1.0"
            ])
            try:
                _MPV_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
                _MPV_PID_FILE.write_text(str(self._mpv_proc.pid))
            except Exception:
                pass
            _write_mpvpaper_autostart(path)
            self._current = str(path)
            self._vid_grid.mark_current(self._current)
            self._refresh_favorite_button()
            self._show_banner(t("Video wallpaper: {name}").format(name=path.name))
            self.main_window.add_toast(Adw.Toast.new(t("Video: {name}").format(name=path.name)))
        except FileNotFoundError:
            self.main_window.add_toast(
                Adw.Toast.new(t("mpvpaper not found — yay -S mpvpaper"))
            )
        except Exception as e:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

    def _stop_mpv(self):
        if self._mpv_proc is not None:
            if self._mpv_proc.poll() is None:
                self._mpv_proc.terminate()
            self._mpv_proc = None
        else:
            # Kein laufender Prozess verfolgt — PID aus vorheriger Sitzung prüfen
            try:
                if _MPV_PID_FILE.exists():
                    pid = int(_MPV_PID_FILE.read_text().strip())
                    os.kill(pid, 15)  # SIGTERM
            except Exception:
                pass
        try:
            _MPV_PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Toolbar-Buttons ───────────────────────────────────────────────────

    def _save_extra(self) -> None:
        self._extra["favorites"] = sorted(self._favorites)
        self._extra["slideshowEnabled"] = self._slideshow_enabled.get_active()
        self._extra["slideshowMinutes"] = int(self._slideshow_interval.get_value())
        atomic_write_json(_EXTRA_SETTINGS, self._extra)

    def _refresh_favorite_button(self) -> None:
        favorite = bool(self._current) and self._current in self._favorites
        self._fav_btn.set_active(favorite)
        self._fav_btn.set_icon_name("starred-symbolic" if favorite else "non-starred-symbolic")

    def _on_favorite_toggled(self, button) -> None:
        if not self._current:
            return
        if button.get_active():
            self._favorites.add(self._current)
        else:
            self._favorites.discard(self._current)
        self._save_extra()
        self._refresh_favorite_button()
        if self._fav_filter.get_active():
            self._reload()

    def _reschedule_slideshow(self) -> None:
        if self._slideshow_source:
            GLib.source_remove(self._slideshow_source)
            self._slideshow_source = 0
        if self._slideshow_enabled.get_active():
            minutes = max(1, int(self._slideshow_interval.get_value()))
            self._slideshow_source = GLib.timeout_add_seconds(
                minutes * 60, self._slideshow_tick
            )

    def _on_slideshow_changed(self, *_args) -> None:
        self._save_extra()
        self._reschedule_slideshow()

    def _slideshow_tick(self) -> bool:
        self._stop_mpv()
        try:
            subprocess.Popen(["caelestia", "wallpaper", "-r", str(_get_image_dir())])
            _write_mpvpaper_autostart(None)
            self.main_window.add_toast(Adw.Toast.new(t("Random wallpaper set")))
        except Exception as exc:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=exc)))
        return True

    def _on_random(self, _):
        self._stop_mpv()
        try:
            subprocess.Popen(["caelestia", "wallpaper", "-r", str(_get_image_dir())])
            _write_mpvpaper_autostart(None)
            self._show_banner(t("Random wallpaper set"))
            self.main_window.add_toast(Adw.Toast.new(t("Random wallpaper set")))
        except Exception as e:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

    def _on_mode_toggled(self, btn):
        mode = "light" if btn.get_active() else "dark"
        self._scheme_mode = mode
        btn.set_icon_name(
            "weather-clear-symbolic" if mode == "light"
            else "weather-clear-night-symbolic"
        )
        try:
            subprocess.Popen(["caelestia", "scheme", "set", "--notify", "-m", mode])
            self._show_banner(t("Colour scheme: {mode}").format(mode=t(mode.capitalize())))
            self.main_window.add_toast(Adw.Toast.new(t("Colour scheme: {mode}").format(mode=t(mode.capitalize()))))
        except Exception as e:
            self.main_window.add_toast(Adw.Toast.new(t("Error: {error}").format(error=e)))

    def _on_clock_changed(self, *_):
        settings = _get_clock_settings()
        settings["enabled"]      = self._clock_enabled.get_active()
        settings["position"]     = self._clock_pos.get_active_id() or "top-right"
        settings["scale"]        = round(self._clock_scale.get_value(), 1)
        settings["invertColors"] = self._clock_invert.get_active()
        _save_clock_settings(settings)

    def _show_banner(self, text: str):
        self.banner.set_title(text)
        self.banner.set_revealed(True)