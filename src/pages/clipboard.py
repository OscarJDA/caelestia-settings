"""Clipboard history via cliphist (D10)."""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from src.lang import t  # noqa: E402


def _run(args: list[str], input_text: str | None = None, timeout: int = 5):
    try:
        return subprocess.run(
            args, input=input_text, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"clipboard command failed: {exc}")
        return None


class ClipboardPage(Adw.PreferencesPage):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._rows: list[Gtk.Widget] = []
        self._entries: list[tuple[str, str]] = []
        self._group = Adw.PreferencesGroup(
            title=t("Clipboard history"),
            description=t("Stored by cliphist. Selecting an entry copies it back to the clipboard."),
        )
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text(t("Refresh history"))
        refresh.connect("clicked", lambda _b: self.refresh())
        self._group.set_header_suffix(refresh)
        self.add(self._group)

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(t("Filter clipboard…"))
        self._search.connect("search-changed", lambda _e: self._render())
        search_group = Adw.PreferencesGroup()
        search_row = Adw.ActionRow(title=t("Search"))
        search_row.add_suffix(self._search)
        search_group.add(search_row)
        self.add(search_group)

        clear_group = Adw.PreferencesGroup()
        clear_row = Adw.ActionRow(title=t("Clear all history"), subtitle=t("This cannot be undone"))
        clear_btn = Gtk.Button(label=t("Clear"))
        clear_btn.add_css_class("destructive-action")
        clear_btn.set_valign(Gtk.Align.CENTER)
        clear_btn.connect("clicked", lambda _b: self._clear_all())
        clear_row.add_suffix(clear_btn)
        clear_group.add(clear_row)
        self.add(clear_group)

        self.refresh()

    def refresh(self) -> None:
        result = _run(["cliphist", "list"])
        self._entries = []
        if result is not None and result.returncode == 0:
            for line in result.stdout.splitlines():
                if "\t" not in line:
                    continue
                entry_id, preview = line.split("\t", 1)
                self._entries.append((entry_id, preview))
        self._render()

    def _render(self) -> None:
        for row in self._rows:
            try:
                self._group.remove(row)
            except Exception:
                pass
        self._rows = []
        query = self._search.get_text().casefold().strip()
        shown = 0
        for entry_id, preview in self._entries:
            if query and query not in preview.casefold():
                continue
            shown += 1
            if shown > 200:
                break
            text = " ".join(preview.split())
            row = Adw.ActionRow(
                title=GLib.markup_escape_text(text[:90] or t("(empty)")),
                subtitle=GLib.markup_escape_text(f"#{entry_id}"),
            )
            copy = Gtk.Button(label=t("Copy"))
            copy.set_valign(Gtk.Align.CENTER)
            copy.connect("clicked", lambda _b, i=entry_id: self._copy(i))
            row.add_suffix(copy)
            delete = Gtk.Button(icon_name="user-trash-symbolic")
            delete.set_valign(Gtk.Align.CENTER)
            delete.add_css_class("flat")
            delete.connect("clicked", lambda _b, i=entry_id: self._delete(i))
            row.add_suffix(delete)
            self._group.add(row)
            self._rows.append(row)

        if not self._rows:
            row = Adw.ActionRow(
                title=t("No clipboard entries") if not query else t("No matches"),
                subtitle=t("Copy something to add it to the history"),
            )
            self._group.add(row)
            self._rows.append(row)

    def _copy(self, entry_id: str) -> None:
        try:
            decoded = subprocess.run(
                ["cliphist", "decode", entry_id], capture_output=True, timeout=5
            )
        except (OSError, subprocess.TimeoutExpired):
            decoded = None
        if decoded is None or decoded.returncode != 0:
            self.main_window.add_toast(Adw.Toast.new(t("Could not decode clipboard entry")))
            return
        try:
            copied = subprocess.run(
                ["wl-copy"],
                input=decoded.stdout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            copied = None
        if copied is None or copied.returncode != 0:
            self.main_window.add_toast(Adw.Toast.new(t("Could not copy to clipboard")))
            return
        self.main_window.add_toast(Adw.Toast.new(t("Copied to clipboard")))

    def _delete(self, entry_id: str) -> None:
        _run(["cliphist", "delete"], input_text=f"{entry_id}\n")
        self.refresh()

    def _clear_all(self) -> None:
        dialog = Adw.AlertDialog(heading=t("Clear clipboard history?"), body=t("All cliphist entries will be deleted."))
        dialog.add_response("cancel", t("Cancel"))
        dialog.add_response("clear", t("Clear"))
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_dialog, response: str) -> None:
            if response == "clear":
                _run(["cliphist", "wipe"])
                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self.get_root())
