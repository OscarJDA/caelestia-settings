"""Global settings search (A3).

The index is built from the declarative schema pages plus a small static
catalogue for the pre-existing pages.  Selecting a result navigates to the
owning page and focuses/highlights the matching row.

The results are shown in an inline revealer below the header instead of a
``Gtk.Popover``.  Popovers are separate Wayland surfaces: showing one takes
keyboard focus away from the search entry (so typing stops after the first
match) and, depending on the compositor, can also swallow pointer events on
the result rows.  An inline panel keeps both keyboard and pointer input in
the same window.
"""

from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from src.settings_engine import SearchEntry  # noqa: E402
from src.lang import t  # noqa: E402


@dataclass
class SearchHit:
    page_id: str
    page_title: str
    label: str
    subtitle: str
    keywords: str
    row: Gtk.Widget | None = None

    def haystack(self) -> str:
        return " ".join((self.label, self.subtitle, self.keywords, self.page_title)).casefold()


STATIC_ENTRIES: tuple[tuple[str, str, str, str, str], ...] = (
    ("home", "Home", "System overview", "Monitors, Wi-Fi, temperatures and wallpaper at a glance", "dashboard glance"),
    ("gen", "General", "Keyboard layout", "Hyprland input layout", "keyboard language layout xkb"),
    ("gen", "General", "NumLock on startup", "input.conf", "numlock keyboard"),
    ("gen", "General", "System language", "Locale via localectl", "locale language"),
    ("gen", "General", "Timezone", "System timezone via timedatectl", "time zone clock"),
    ("wall", "Wallpaper", "Wallpaper", "Browse images and videos, random wallpaper", "background picture video"),
    ("wall", "Wallpaper", "Light / dark mode", "Caelestia colour scheme", "theme scheme light dark"),
    ("wall", "Wallpaper", "Desktop clock", "Show, position, size and invert colors", "clock desktop"),
    ("ws", "Workspaces", "Workspaces", "Add, remove, reorder and assign workspaces", "workspace monitor default persistent"),
    ("mon", "Monitor", "Monitor arrangement", "Resolution, refresh rate, rotation and scale", "display resolution refresh rotation scale"),
    ("mon", "Monitor", "Variable refresh rate", "VRR / FreeSync / adaptive sync", "vrr freesync adaptive sync"),
    ("mon", "Monitor", "Mirror display", "Show the same image as another monitor", "mirror duplicate clone"),
    ("mon", "Monitor", "Bit depth and HDR", "8-bit, 10-bit and HDR output", "hdr bit depth 10bit colour"),
    ("mon", "Monitor", "Primary monitor", "Primary output selection", "primary xrandr"),
    ("mon", "Monitor", "Taskbar visibility", "Show or hide the bar per monitor", "bar taskbar persistent"),
    ("wifi", "WLAN", "Wi-Fi networks", "Scan, connect and disconnect", "wifi wireless network password"),
    ("bluetooth", "Bluetooth", "Bluetooth devices", "Scan, pair, connect, trust and forget", "bt adapter wireless"),
    ("audio", "Audio", "Audio output", "Default output device and volume", "sound speaker volume"),
    ("rules", "Window Rules", "Window rules", "Assign apps to workspaces and float them", "window rule app workspace float"),
    ("rules", "Window Rules", "Advanced window rules", "Size, position, opacity, blur, pin, tags and more", "advanced window rules size opacity pin tag"),
    ("rules", "Window Rules", "Rule tester", "See which open windows match your rules", "test rules windows match"),
    ("keys", "Keybinds", "Keybinds", "View and edit Hyprland shortcuts", "shortcut bind hotkey"),
    ("hypr-options", "Hyprland: All Options", "All Hyprland options", "Search every raw compositor option", "advanced options raw hyprland all"),
    ("fans", "Fans", "Fan control", "GPU and system fans, temperatures and curves", "fan temperature gpu pwm"),
    ("upd", "Updates", "System updates", "Update packages and the app", "update upgrade pacman"),
    ("profiles", "Profiles", "Export profile", "Back up shell, overrides, monitors and keybinds", "backup export import restore profile"),
    ("diag", "Diagnostics", "Run Hyprland doctor", "Validate config, check errors and reload", "doctor diagnose config errors validate"),
    ("display", "Display", "Brightness", "Backlight, night light and DDC/CI monitors", "brightness backlight night light gamma ddc"),
    ("theming", "Theming", "Scheme", "Colour scheme, flavour, mode and variant", "theme scheme colours palette accent"),
    ("theming", "Theming", "Colour scheme", "Scheme, flavour, mode and variants", "theme scheme colours palette accent"),
    ("network", "Network", "Ethernet and VPN", "Devices, VPN connections, hotspot and IPv4", "ethernet vpn hotspot ip dns"),
    ("apps", "Default Apps", "Default applications", "Terminal, browser, editor and file manager", "default apps terminal browser editor"),
    ("login-theme", "Login Theme", "SDDM login screen", "Welcome message, avatar, blur and clock", "sddm login theme welcome avatar"),
    ("clipboard", "Clipboard", "Clipboard history", "Browse, copy and delete cliphist entries", "clipboard cliphist copy paste"),
    ("capture", "Capture", "Screenshots and recording", "grim, slurp and wf-recorder", "screenshot record wf-recorder grim slurp"),
    ("sys-services", "System Services", "user services", "Start, stop, enable and disable systemd user services", "systemd service user enable disable"),
    ("editor", "Config Editor", "Raw config editor", "Edit Lua, JSON and previewed configuration files", "raw edit lua json config file"),
    ("about", "About", "About", "Version and self-update", "version about"),
)


class SearchIndex:
    def __init__(self) -> None:
        self._entries: list[SearchHit] = []

    def add(self, entry: SearchEntry | SearchHit) -> None:
        if isinstance(entry, SearchEntry):
            hit = SearchHit(
                page_id=entry.page_id,
                page_title=entry.page_title,
                label=entry.label,
                subtitle=entry.subtitle,
                keywords=entry.keywords,
                row=entry.row,
            )
        else:
            hit = entry
        self._entries.append(hit)

    def add_static_catalogue(self) -> None:
        for page_id, page_title, label, subtitle, keywords in STATIC_ENTRIES:
            self.add(SearchHit(page_id, t(page_title), t(label), t(subtitle), keywords))

    def search(self, query: str, limit: int = 30) -> list[SearchHit]:
        tokens = [token for token in query.casefold().split() if token]
        if not tokens:
            return []

        scored: list[tuple[int, SearchHit]] = []
        for entry in self._entries:
            haystack = entry.haystack()
            if not all(token in haystack for token in tokens):
                continue
            label = entry.label.casefold()
            if label == query.casefold():
                score = 4
            elif label.startswith(tokens[0]):
                score = 3
            elif tokens[0] in label:
                score = 2
            else:
                score = 1
            scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1].page_title.casefold(), item[1].label.casefold()))
        return [entry for _score, entry in scored[:limit]]


class SettingsSearch:
    """Search entry plus an inline results panel for the main window."""

    def __init__(self, main_window, index: SearchIndex) -> None:
        self.main_window = main_window
        self.index = index
        self.entry = Gtk.SearchEntry()
        self.entry.set_placeholder_text(t("Search settings…"))
        self.entry.set_width_chars(28)
        self.entry.connect("search-changed", self._on_changed)
        self.entry.connect("stop-search", self._on_stop)
        self.entry.connect("activate", self._on_activate_entry)

        self.results_revealer = Gtk.Revealer()
        self.results_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.results_revealer.set_reveal_child(False)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_max_content_height(360)
        self.scroller.set_propagate_natural_height(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.add_css_class("boxed-list")
        self.listbox.connect("row-activated", self._on_row_activated)
        self._results: list[SearchHit] = []
        self.scroller.set_child(self.listbox)

        frame = Gtk.Frame()
        frame.add_css_class("card")
        frame.set_margin_start(12)
        frame.set_margin_end(12)
        frame.set_margin_top(2)
        frame.set_margin_bottom(8)
        frame.set_child(self.scroller)
        self.results_revealer.set_child(frame)

    def _clear(self) -> None:
        child = self.listbox.get_first_child()
        while child is not None:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()

    def _on_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip()
        self._clear()
        if not query:
            self._hide_results()
            return

        hits = self.index.search(query)
        self._results = hits
        if not hits:
            row = Adw.ActionRow(title=t("No results"), subtitle=t("Nothing matches “{query}”").format(query=query))
            row.set_activatable(False)
            self.listbox.append(row)
            self.scroller.set_size_request(-1, 96)
        else:
            for hit in hits:
                subtitle = hit.page_title
                if hit.subtitle:
                    subtitle = f"{hit.page_title} · {hit.subtitle}"
                row = Adw.ActionRow(title=hit.label, subtitle=subtitle)
                row.set_activatable(True)
                row.connect("activated", lambda _row, h=hit: self._activate(h))
                self.listbox.append(row)
            self.scroller.set_size_request(-1, min(360, max(110, len(hits) * 54)))
        self.results_revealer.set_reveal_child(True)

    def _hide_results(self) -> None:
        self.results_revealer.set_reveal_child(False)
        self._clear()
        self._results = []

    def hide_results(self) -> None:
        self._hide_results()

    def _activate(self, hit: SearchHit) -> None:
        self._hide_results()
        self.entry.set_text("")
        self.main_window.navigate(hit.page_id, hit.row)

    def _on_row_activated(self, _listbox, row) -> None:
        index = row.get_index()
        if 0 <= index < len(self._results):
            self._activate(self._results[index])

    def _on_activate_entry(self, _entry) -> None:
        if self._results:
            self._activate(self._results[0])

    def _on_stop(self, _entry) -> None:
        self._hide_results()
        self.entry.set_text("")

    def focus(self) -> None:
        self.entry.grab_focus()
        self.entry.select_region(0, -1)
