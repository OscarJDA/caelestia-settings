from src.hypr_settings import HyprBackend
from src.settings_engine import SettingsPage, make_backend_error_toast
from src.settings_schema import HYPR_DECORATION_SPEC


class HyprDecorationPage(SettingsPage):
    def __init__(self, main_window, backend=None):
        backend = backend or HyprBackend(error_sink=make_backend_error_toast(main_window))
        super().__init__(main_window, HYPR_DECORATION_SPEC, backend)
