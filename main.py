#!/usr/bin/env python
import sys
import traceback

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw  # noqa: E402

from src.config import get_config_dir  # noqa: E402
from src.window import MainWindow  # noqa: E402


def _extract_initial_page(argv: list[str]) -> tuple[str | None, list[str]]:
    """Support ``--page bar`` and ``--page=bar`` deep links.

    GApplication rejects unknown options, so the page arguments are removed
    before the remaining argv is handed to ``app.run``.
    """
    page = None
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--page":
            if index + 1 < len(argv):
                page = argv[index + 1]
                index += 2
                continue
            index += 1
            continue
        if arg.startswith("--page="):
            page = arg.split("=", 1)[1] or None
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return page, remaining


class SettingsApp(Adw.Application):
    def __init__(self, initial_page: str | None = None, **kwargs):
        get_config_dir()
        self.initial_page = initial_page
        super().__init__(application_id="org.caelestia.settings", **kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        try:
            self.win = MainWindow(application=app, initial_page=self.initial_page)
            self.win.present()
        except Exception as exc:
            # Never leave a headless primary instance behind: show the error
            # in a window so the user (and the console) can see what failed.
            traceback.print_exc()
            self.win = Adw.ApplicationWindow(application=app)
            self.win.set_title("Caelestia Settings – startup error")
            self.win.set_default_size(620, 420)
            page = Adw.StatusPage(
                icon_name="dialog-error-symbolic",
                title="Caelestia Settings could not start",
                description=str(exc) or exc.__class__.__name__,
            )
            self.win.set_content(page)
            self.win.present()


if __name__ == "__main__":
    initial_page, remaining_args = _extract_initial_page(sys.argv[1:])
    app = SettingsApp(initial_page=initial_page)
    sys.exit(app.run([sys.argv[0], *remaining_args]))
