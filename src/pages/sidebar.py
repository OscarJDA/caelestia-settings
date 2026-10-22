from src.config import CAELESTIA_SHELL_JSON
from src.settings_editors import FieldSpec, add_id_list, add_object_list
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import (
    QUICK_TOGGLE_CHOICES,
    QUICK_TOGGLE_DEFAULTS,
    SIDEBAR_UTILITIES_SPEC,
)

VPN_PROVIDER_FIELDS = [
    FieldSpec("id", "Identifier", subtitle="Unique ID used by the selected provider"),
    FieldSpec("name", "Name"),
    FieldSpec("displayName", "Display name"),
    FieldSpec("interface", "Network interface", subtitle="e.g. wg0 or tun0"),
    FieldSpec("connectCmd", "Connect command", kind="command"),
    FieldSpec("disconnectCmd", "Disconnect command", kind="command"),
]


class SidebarUtilitiesPage(SettingsPage):
    def __init__(self, main_window):
        backend = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(
            main_window,
            SIDEBAR_UTILITIES_SPEC,
            backend,
            custom_builders=[self._build_custom],
        )

    def _build_custom(self, page):
        backend = self.backend
        add_id_list(
            page,
            backend,
            "utilities.quickToggles",
            QUICK_TOGGLE_DEFAULTS,
            QUICK_TOGGLE_CHOICES,
            "Quick toggles",
            "Order and visibility of the quick toggle buttons.",
            allow_duplicates=False,
        )
        add_object_list(
            page,
            backend,
            "utilities.vpn.provider",
            [],
            VPN_PROVIDER_FIELDS,
            "VPN providers",
            "Providers available in the quick settings VPN toggle.",
            title_key="displayName",
            new_item={
                "id": "",
                "name": "",
                "displayName": "New provider",
                "interface": "",
                "connectCmd": [],
                "disconnectCmd": [],
            },
        )
