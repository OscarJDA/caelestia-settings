from src.config import CAELESTIA_SHELL_JSON
from src.settings_editors import add_icon_rules, add_id_list, add_string_list
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import (
    BAR_ENTRY_CHOICES,
    BAR_ENTRY_DEFAULTS,
    BAR_SPEC,
    BAR_STATUS_CHOICES,
    BAR_STATUS_DEFAULTS,
    SPECIAL_WORKSPACE_ICON_DEFAULTS,
    WINDOW_ICON_DEFAULTS,
)


class BarPage(SettingsPage):
    def __init__(self, main_window):
        backend = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(main_window, BAR_SPEC, backend, custom_builders=[self._build_custom])

    def _build_custom(self, page):
        backend = self.backend

        add_id_list(
            page,
            backend,
            "bar.entries",
            BAR_ENTRY_DEFAULTS,
            BAR_ENTRY_CHOICES,
            "Bar entries",
            "Order and visibility of the bar widgets. Drag to reorder.",
            allow_duplicates=True,
        )
        add_id_list(
            page,
            backend,
            "bar.statusIcons",
            BAR_STATUS_DEFAULTS,
            BAR_STATUS_CHOICES,
            "Status icons",
            "Icons shown on the right side of the bar.",
            allow_duplicates=False,
        )
        add_icon_rules(
            page,
            backend,
            "bar.workspaces.workspaceIcons",
            [],
            "Workspace icons",
            "Exact-name or regex rules that replace workspace labels with icons.",
        )
        add_icon_rules(
            page,
            backend,
            "bar.workspaces.specialWorkspaceIcons",
            SPECIAL_WORKSPACE_ICON_DEFAULTS,
            "Special workspace icons",
            "Icons for named special workspaces.",
        )
        add_icon_rules(
            page,
            backend,
            "bar.workspaces.windowIcons",
            WINDOW_ICON_DEFAULTS,
            "Window icons",
            "Class regex rules used for the icons next to workspaces.",
        )
        add_string_list(
            page,
            backend,
            "bar.excludedScreens",
            [],
            "Excluded screens",
            "Monitor names where the bar should not be shown.",
            "Add monitor name (e.g. DP-1)",
        )
        add_string_list(
            page,
            backend,
            "bar.tray.hiddenIcons",
            [],
            "Hidden tray icons",
            "Tray item identifiers that should stay hidden.",
            "Add tray icon id",
        )
        add_string_list(
            page,
            backend,
            "bar.workspaces.ignoredTags",
            ["hide_in_bar", "xwl_popup"],
            "Ignored window tags",
            "Windows carrying these tags are skipped in the bar.",
            "Add tag",
        )
