import json
import threading
import urllib.error
import urllib.request

from gi.repository import Adw, Gdk, GLib, Gtk

from src.hypr_settings import HyprBackend
from src.lang import t
from src.pages.about import AboutPage
from src.pages.appearance import AppearancePage
from src.pages.audio import AudioPage
from src.pages.bar import BarPage
from src.pages.bluetooth import BluetoothPage
from src.pages.capture import CapturePage
from src.pages.clipboard import ClipboardPage
from src.pages.config_editor import ConfigEditorPage
from src.pages.dashboard import DashboardPage
from src.pages.default_apps import DefaultAppsPage
from src.pages.desktop_widgets import DesktopWidgetsPage
from src.pages.diagnostics import DiagnosticsPage
from src.pages.display import DisplayPage
from src.pages.fans import FansPage
from src.pages.general import GeneralPage
from src.pages.home import HomePage
from src.pages.hypr_animations import AnimationsPage
from src.pages.hypr_decoration import HyprDecorationPage
from src.pages.hypr_general import HyprGeneralPage
from src.pages.hypr_gestures import GesturesPage
from src.pages.hypr_input import HyprInputPage
from src.pages.hypr_options import HyprOptionsPage
from src.pages.keybinds import KeybindsPage
from src.pages.launcher import LauncherPage
from src.pages.lock import LockPage
from src.pages.login_theme import LoginThemePage
from src.pages.monitor import MonitorPage
from src.pages.monitor_overrides import MonitorOverridePage, list_monitors
from src.pages.network import NetworkPage
from src.pages.notifications import NotificationsPage
from src.pages.power import PowerPage
from src.pages.profiles import ProfilesPage
from src.pages.services import ServicesPage
from src.pages.sidebar import SidebarUtilitiesPage
from src.pages.system_services import SystemServicesPage
from src.pages.theming import ThemingPage
from src.pages.typography import TypographyPage
from src.pages.updates import UpdatePage
from src.pages.wallpaper import WallpaperPage
from src.pages.wifi import WifiPage
from src.pages.window_rules import WindowRulesPage
from src.pages.workspaces import WorkspacesPage
from src.safe_io import HISTORY
from src.search import SearchIndex, SettingsSearch
from src.settings_engine import apply_search_highlight, make_backend_error_toast

# Source of truth for "is a newer version out": the manifest.json committed
# on main (the prod branch, see branching policy — dev is pre-release).
MANIFEST_URL = "https://raw.githubusercontent.com/OscarJDA/caelestia-settings/main/manifest.json"

PAGE_ALIASES = {
    "hypr": "hypr-general",
    "hyprland": "hypr-general",
    "decor": "hypr-decor",
    "decoration": "hypr-decor",
    "input": "hypr-input",
    "anim": "hypr-anim",
    "animations": "hypr-anim",
    "gestures": "hypr-gestures",
    "options": "hypr-options",
    "all-options": "hypr-options",
    "advanced": "hypr-options",
    "fonts": "typography",
    "shell": "appearance",
    "bt": "bluetooth",
    "notifs": "notifications",
    "idle": "power",
    "utilities": "sidebar",
    "backup": "profiles",
    "export": "profiles",
    "doctor": "diag",
    "diagnostics": "diag",
    "theme": "theming",
    "theming": "theming",
    "brightness": "display",
    "night": "display",
    "net": "network",
    "clip": "clipboard",
    "record": "capture",
    "default-apps": "apps",
    "login": "login-theme",
    "sddm": "login-theme",
    "systemd": "sys-services",
    "services-user": "sys-services",
    "raw": "editor",
    "config": "editor",
    "widgets": "widgets",
    "desktop": "widgets",
    "desktop-widgets": "widgets",
}


def _parse_version(version: str) -> tuple:
    """Turns "1.2.10" into (1, 2, 10) for numeric comparison.

    Plain string comparison would rank "1.10.0" below "1.9.0". Returns an
    empty tuple for anything that isn't dot-separated integers, which always
    compares as "not newer" against a real version.
    """
    try:
        return tuple(int(part) for part in version.split("."))
    except (ValueError, AttributeError):
        return ()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, initial_page: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.set_title(t("Caelestia Settings"))
        self.set_default_size(1100, 840)
        self.initial_page = initial_page
        self.pages: dict[str, Gtk.Widget] = {}

        # --- ToastOverlay als Haupt-Container ---
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(root)

        self.header = Adw.HeaderBar()
        root.append(self.header)

        # --- BUTTONS ---
        self.update_btn = Gtk.Button(label=t("Update App"))
        self.update_btn.add_css_class("suggested-action")
        self.update_btn.set_visible(False)
        self.update_btn.connect("clicked", self.on_update_app)
        self.header.pack_end(self.update_btn)

        self.undo_btn = Gtk.Button(icon_name="edit-undo-symbolic")
        self.undo_btn.set_tooltip_text(t("Undo last change (Ctrl+Z)"))
        self.undo_btn.set_sensitive(False)
        self.undo_btn.connect("clicked", self.on_undo)
        self.header.pack_start(self.undo_btn)

        self.redo_btn = Gtk.Button(icon_name="edit-redo-symbolic")
        self.redo_btn.set_tooltip_text(t("Redo change (Ctrl+Shift+Z)"))
        self.redo_btn.set_sensitive(False)
        self.redo_btn.connect("clicked", self.on_redo)
        self.header.pack_start(self.redo_btn)

        self.preview_toggle = Gtk.ToggleButton(label=t("Preview"))
        self.preview_toggle.set_tooltip_text(t("Preview changes and revert automatically after 15 seconds"))
        self.preview_toggle.connect("notify::active", self._on_preview_toggled)
        self.header.pack_start(self.preview_toggle)

        self.preview_bar = Gtk.Revealer()
        self.preview_bar.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        preview_box.add_css_class("card")
        preview_box.set_margin_top(6)
        preview_box.set_margin_bottom(6)
        preview_box.set_margin_start(12)
        preview_box.set_margin_end(12)
        preview_icon = Gtk.Image.new_from_icon_name("camera-photo-symbolic")
        preview_box.append(preview_icon)
        self._preview_label = Gtk.Label(label=t("Preview"))
        self._preview_label.set_hexpand(True)
        self._preview_label.set_halign(Gtk.Align.START)
        preview_box.append(self._preview_label)
        revert_btn = Gtk.Button(label=t("Revert now"))
        revert_btn.connect("clicked", lambda _b: self._revert_preview())
        preview_box.append(revert_btn)
        keep_btn = Gtk.Button(label=t("Keep changes"))
        keep_btn.add_css_class("suggested-action")
        keep_btn.connect("clicked", lambda _b: self._keep_preview())
        preview_box.append(keep_btn)
        self.preview_bar.set_child(preview_box)
        root.append(self.preview_bar)

        self._preview_timer = 0
        self._preview_seconds = 0
        self._preview_active = False
        self._preview_start_count = 0

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_vexpand(True)
        root.append(main_box)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self.stack)

        sidebar_scroller = Gtk.ScrolledWindow()
        sidebar_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroller.set_size_request(200, -1)
        sidebar_scroller.set_vexpand(True)
        sidebar_scroller.set_child(sidebar)

        main_box.append(sidebar_scroller)
        main_box.append(self.stack)

        # Pages that other pages depend on (HomePage reads about_page).
        self.mon_page = MonitorPage(self)
        self.about_page = AboutPage(self)

        # One shared Hyprland backend keeps the per-option cache warm across
        # the three Hyprland pages instead of shelling out for every row.
        self.hypr_backend = HyprBackend(error_sink=make_backend_error_toast(self))
        hypr_backend = self.hypr_backend
        hypr_backend.ensure_loaded()

        # ── Stack befüllen ──────────────────────────────────────────────────
        self._add_page("home", HomePage(self), t("Home"))
        self._add_page("gen", GeneralPage(self), t("General"))
        self._add_page("display", DisplayPage(self), t("Display"))
        self._add_page("appearance", AppearancePage(self), t("Appearance"))
        self._add_page("theming", ThemingPage(self), t("Theming"))
        self._add_page("typography", TypographyPage(self), t("Typography"))
        self._add_page("bar", BarPage(self), t("Bar"))
        self._add_page("widgets", DesktopWidgetsPage(self), t("Desktop Widgets"))
        self._add_page("launcher", LauncherPage(self), t("Launcher"))
        self._add_page("dashboard", DashboardPage(self), t("Dashboard"))
        self._add_page("sidebar", SidebarUtilitiesPage(self), t("Sidebar & Utilities"))
        self._add_page("clipboard", ClipboardPage(self), t("Clipboard"))
        self._add_page("capture", CapturePage(self), t("Capture"))
        self._add_page("notifications", NotificationsPage(self), t("Notifications"))
        self._add_page("lock", LockPage(self), t("Lock Screen"))
        self._add_page("login-theme", LoginThemePage(self), t("Login Theme"))
        self._add_page("power", PowerPage(self), t("Power & Idle"))
        self._add_page("services", ServicesPage(self), t("Services"))
        self._add_page("apps", DefaultAppsPage(self), t("Default Apps"))
        self._add_page("hypr-general", HyprGeneralPage(self, backend=hypr_backend), t("Hyprland: General"))
        self._add_page("hypr-decor", HyprDecorationPage(self, backend=hypr_backend), t("Hyprland: Decoration"))
        self._add_page("hypr-input", HyprInputPage(self, backend=hypr_backend), t("Hyprland: Input"))
        self._add_page("hypr-anim", AnimationsPage(self, backend=hypr_backend), t("Hyprland: Animations"))
        self._add_page("hypr-gestures", GesturesPage(self, backend=hypr_backend), t("Hyprland: Gestures"))
        self._add_page("hypr-options", HyprOptionsPage(self, backend=hypr_backend), t("Hyprland: All Options"))
        self._add_page("wall", WallpaperPage(self), t("Wallpaper"))
        self._add_page("ws", WorkspacesPage(self), t("Workspaces"))
        self._add_page("mon", self.mon_page, t("Monitor"))
        for monitor_name in list_monitors():
            self._add_page(
                f"overrides-{monitor_name}",
                MonitorOverridePage(self, monitor_name),
                f"{t('Overrides')}: {monitor_name}",
            )
        self._add_page("rules", WindowRulesPage(self), t("Window Rules"))
        self._add_page("keys", KeybindsPage(self), t("Keybinds"))
        self._add_page("bluetooth", BluetoothPage(self), t("Bluetooth"))
        self._add_page("network", NetworkPage(self), t("Network"))
        self._add_page("wifi", WifiPage(self), t("WLAN"))
        self._add_page("audio", AudioPage(self), t("Audio"))
        self._add_page("fans", FansPage(self), t("Fans"))
        self._add_page("upd", UpdatePage(self), t("Updates"))
        self._add_page("sys-services", SystemServicesPage(self), t("System Services"))
        self._add_page("profiles", ProfilesPage(self), t("Profiles"))
        self._add_page("diag", DiagnosticsPage(self), t("Diagnostics"))
        self._add_page("editor", ConfigEditorPage(self), t("Config Editor"))
        self._add_page("about", self.about_page, t("About"))
        # ───────────────────────────────────────────────────────────────────

        self.stack.set_visible_child_name("home")

        self._install_css()
        self._install_shortcuts()
        self._build_search()
        self._refresh_history_buttons()
        HISTORY.add_listener(self._refresh_history_buttons)

        if self.initial_page:
            GLib.idle_add(lambda: (self.navigate(self.initial_page), False)[1])

        threading.Thread(target=self._check_for_update, daemon=True).start()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _add_page(self, page_id: str, widget: Gtk.Widget, title: str) -> None:
        self.pages[page_id] = widget
        self.stack.add_titled(widget, page_id, title)

    def _build_search(self) -> None:
        self.search_index = SearchIndex()
        self.search_index.add_static_catalogue()
        for page in self.pages.values():
            if hasattr(page, "search_items"):
                try:
                    for item in page.search_items():
                        self.search_index.add(item)
                except Exception as exc:
                    print(f"Search index failed for {page}: {exc}")
        self.search = SettingsSearch(self, self.search_index)
        self.header.set_title_widget(self.search.entry)
        # Results live in the same window (below the header), so the search
        # entry keeps keyboard focus and the rows receive pointer clicks.
        results_parent = self.header.get_parent()
        if results_parent is not None and hasattr(results_parent, "insert_child_after"):
            results_parent.insert_child_after(self.search.results_revealer, self.header)

    def _install_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        provider = Gtk.CssProvider()
        provider.load_from_data(
            b".search-highlight { background-color: rgba(120, 160, 255, 0.25); border-radius: 12px; }"
        )
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _install_shortcuts(self) -> None:
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)

        def add(accel: str, callback) -> None:
            trigger = Gtk.ShortcutTrigger.parse_string(accel)
            action = Gtk.CallbackAction.new(lambda *_args: (callback(), True)[1])
            controller.add_shortcut(Gtk.Shortcut.new(trigger, action))

        add("<Control>z", lambda: self.on_undo(None))
        add("<Control><Shift>z", lambda: self.on_redo(None))
        add("<Control>y", lambda: self.on_redo(None))
        add("<Control>r", self.reload_current_page)
        add("<Control>f", lambda: self.search.focus() if hasattr(self, "search") else None)
        self.add_controller(controller)

    # ── Navigation & search ────────────────────────────────────────────────

    def navigate(self, page_id: str, row: Gtk.Widget | None = None) -> bool:
        if hasattr(self, "search"):
            self.search.hide_results()
        page_id = PAGE_ALIASES.get(page_id, page_id)
        if page_id == "overrides":
            page_id = next((key for key in self.pages if key.startswith("overrides-")), page_id)
        if page_id not in self.pages:
            self.add_toast(Adw.Toast.new(t("Unknown settings page: {page}").format(page=page_id)))
            return False
        self.stack.set_visible_child_name(page_id)
        page = self.pages[page_id]
        if row is None:
            if hasattr(page, "focus_default"):
                page.focus_default()
        elif hasattr(page, "highlight"):
            GLib.idle_add(lambda: (page.highlight(row), False)[1])
        else:
            GLib.idle_add(lambda: (apply_search_highlight(row), False)[1])
        return True

    def add_toast(self, toast):
        self.toast_overlay.add_toast(toast)

    # ── Undo / redo ────────────────────────────────────────────────────────

    def _refresh_history_buttons(self) -> None:
        self.undo_btn.set_sensitive(HISTORY.can_undo)
        self.redo_btn.set_sensitive(HISTORY.can_redo)
        undo_label = HISTORY.next_undo_label()
        redo_label = HISTORY.next_redo_label()
        self.undo_btn.set_tooltip_text(
            t("Undo: {label} (Ctrl+Z)").format(label=undo_label) if undo_label else t("Nothing to undo (Ctrl+Z)")
        )
        self.redo_btn.set_tooltip_text(
            t("Redo: {label} (Ctrl+Shift+Z)").format(label=redo_label) if redo_label else t("Nothing to redo (Ctrl+Shift+Z)")
        )

    def on_undo(self, _button=None) -> None:
        label = HISTORY.undo()
        if label:
            self.add_toast(Adw.Toast.new(t("Undone: {label}").format(label=label)))
            self._refresh_current_page()

    def on_redo(self, _button=None) -> None:
        label = HISTORY.redo()
        if label:
            self.add_toast(Adw.Toast.new(t("Redone: {label}").format(label=label)))
            self._refresh_current_page()

    def _refresh_current_page(self) -> None:
        page = self.stack.get_visible_child()
        if hasattr(page, "reload_values"):
            page.reload_values()

    # ── Preview mode ───────────────────────────────────────────────────────

    def _on_preview_toggled(self, button, _pspec) -> None:
        if not button.get_active():
            self._keep_preview(show_toast=False)

    def preview_changed(self, label: str = "settings") -> None:
        """Called after a change when preview mode is enabled."""
        if not self.preview_toggle.get_active():
            return
        if not self._preview_active:
            self._preview_active = True
            # The change has already been pushed, so the batch starts one
            # entry before the current stack size.
            self._preview_start_count = max(0, HISTORY.undo_count - 1)
            self.preview_bar.set_reveal_child(True)
        self._preview_label.set_text(t("Preview — {label}").format(label=label))
        self._preview_seconds = 15
        self._preview_label.set_text(
            t("Preview — {label} · reverting in {seconds}s").format(label=label, seconds=self._preview_seconds)
        )
        if self._preview_timer:
            GLib.source_remove(self._preview_timer)
        self._preview_timer = GLib.timeout_add_seconds(1, self._preview_tick)

    def _preview_tick(self) -> bool:
        self._preview_seconds -= 1
        text = self._preview_label.get_text().split(" · ")[0]
        if self._preview_seconds <= 0:
            self._preview_timer = 0
            self._revert_preview()
            return False
        self._preview_label.set_text(t("{text} · reverting in {seconds}s").format(text=text, seconds=self._preview_seconds))
        return True

    def _cancel_preview_timer(self) -> None:
        if self._preview_timer:
            GLib.source_remove(self._preview_timer)
            self._preview_timer = 0

    def _keep_preview(self, show_toast: bool = True) -> None:
        self._cancel_preview_timer()
        self._preview_active = False
        self.preview_bar.set_reveal_child(False)
        if show_toast:
            self.add_toast(Adw.Toast.new(t("Preview changes kept")))

    def _revert_preview(self) -> None:
        self._cancel_preview_timer()
        reverted = 0
        while HISTORY.undo_count > self._preview_start_count and HISTORY.can_undo:
            if HISTORY.undo() is None:
                break
            reverted += 1
        self._preview_active = False
        self.preview_bar.set_reveal_child(False)
        self._refresh_current_page()
        self.add_toast(Adw.Toast.new(t("Reverted {count} preview change(s)").format(count=reverted)))

    def reload_current_page(self) -> None:
        """Discard cached Hyprland values and re-read the current page."""
        if hasattr(self, "hypr_backend"):
            self.hypr_backend.invalidate()
        self._refresh_current_page()
        self.add_toast(Adw.Toast.new(t("Values reloaded")))

    # ── Update check ───────────────────────────────────────────────────────

    def _check_for_update(self):
        try:
            with urllib.request.urlopen(MANIFEST_URL, timeout=5) as resp:
                remote_manifest = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return  # No network, GitHub unreachable, etc. — check silently fails.

        remote_version = _parse_version(remote_manifest.get("version", ""))
        local_version = _parse_version(self.about_page.local_version)
        if remote_version > local_version:
            GLib.idle_add(self.update_btn.set_visible, True)

    def on_update_app(self, btn):
        # The header button is just a shortcut to the same update flow the
        # About page offers — no separate implementation to keep in sync.
        self.about_page.on_update_clicked(btn)
