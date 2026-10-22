from src.config import CAELESTIA_SHELL_JSON
from src.settings_editors import FieldSpec, add_object_list, add_string_list
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import LAUNCHER_SPEC

LAUNCHER_ACTION_DEFAULTS = [
    {"name": "Calculator", "icon": "calculate", "description": "Do simple maths equations (powered by Qalc)", "command": ["autocomplete", "calc"], "enabled": True, "dangerous": False},
    {"name": "Scheme", "icon": "palette", "description": "Change the current colour scheme", "command": ["autocomplete", "scheme"], "enabled": True, "dangerous": False},
    {"name": "Wallpaper", "icon": "image", "description": "Change the current wallpaper", "command": ["autocomplete", "wallpaper"], "enabled": True, "dangerous": False},
    {"name": "Variant", "icon": "colors", "description": "Change the current scheme variant", "command": ["autocomplete", "variant"], "enabled": True, "dangerous": False},
    {"name": "Random", "icon": "casino", "description": "Switch to a random wallpaper", "command": ["caelestia", "wallpaper", "-r"], "enabled": True, "dangerous": False},
    {"name": "Light", "icon": "light_mode", "description": "Change the scheme to light mode", "command": ["setMode", "light"], "enabled": True, "dangerous": False},
    {"name": "Dark", "icon": "dark_mode", "description": "Change the scheme to dark mode", "command": ["setMode", "dark"], "enabled": True, "dangerous": False},
    {"name": "Shutdown", "icon": "power_settings_new", "description": "Shutdown the system", "command": ["poweroff"], "enabled": True, "dangerous": True},
    {"name": "Reboot", "icon": "cached", "description": "Reboot the system", "command": ["reboot"], "enabled": True, "dangerous": True},
    {"name": "Logout", "icon": "exit_to_app", "description": "Log out of the current session", "command": ["logout"], "enabled": True, "dangerous": True},
    {"name": "Lock", "icon": "lock", "description": "Lock the current session", "command": ["loginctl", "lock-session"], "enabled": True, "dangerous": False},
    {"name": "Sleep", "icon": "bedtime", "description": "Suspend then hibernate", "command": ["suspendThenHibernate"], "enabled": True, "dangerous": False},
    {"name": "Settings", "icon": "settings", "description": "Configure the shell", "command": ["caelestia", "shell", "nexus", "open"], "enabled": True, "dangerous": False},
]

LAUNCHER_ACTION_FIELDS = [
    FieldSpec("name", "Name"),
    FieldSpec("icon", "Material icon"),
    FieldSpec("description", "Description"),
    FieldSpec("command", "Command", kind="command", subtitle="Space-separated command and arguments"),
    FieldSpec("enabled", "Enabled", kind="bool", default=True),
    FieldSpec("dangerous", "Mark as dangerous", kind="bool", default=False),
]


class LauncherPage(SettingsPage):
    def __init__(self, main_window):
        backend = ShellBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(main_window, LAUNCHER_SPEC, backend, custom_builders=[self._build_custom])

    def _build_custom(self, page):
        backend = self.backend
        add_object_list(
            page,
            backend,
            "launcher.actions",
            LAUNCHER_ACTION_DEFAULTS,
            LAUNCHER_ACTION_FIELDS,
            "Launcher actions",
            "Searchable actions shown with the action prefix.",
            title_key="name",
            new_item={
                "name": "New action",
                "icon": "star",
                "description": "",
                "command": [],
                "enabled": True,
                "dangerous": False,
            },
        )
        add_string_list(
            page,
            backend,
            "launcher.favouriteApps",
            [],
            "Favourite applications",
            "Desktop IDs pinned to the top of the launcher (e.g. firefox.desktop).",
            "Add desktop ID",
        )
        add_string_list(
            page,
            backend,
            "launcher.hiddenApps",
            [],
            "Hidden applications",
            "Desktop IDs that should not appear in the launcher.",
            "Add desktop ID",
        )
