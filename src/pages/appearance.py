from src.config import CAELESTIA_SHELL_JSON
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import APPEARANCE_SPEC


class AppearancePage(SettingsPage):
    def __init__(self, main_window):
        backend = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(main_window, APPEARANCE_SPEC, backend)
