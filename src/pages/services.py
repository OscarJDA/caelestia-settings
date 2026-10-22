import copy

from src.config import CAELESTIA_SHELL_JSON, hyprctl_reload
from src.hypr_vars import get_hypr_variable, set_hypr_variable
from src.lang import t
from src.safe_io import HISTORY, atomic_write_json, read_json
from src.settings_core import delete_path, get_path, set_path
from src.settings_editors import FieldSpec, add_object_list
from src.settings_engine import SettingsPage, ShellBackend, make_backend_error_toast
from src.settings_schema import SERVICES_SPEC

PLAYER_ALIAS_DEFAULTS = [
    {"from": "com.github.th_ch.youtube_music", "to": "YT Music"},
]

PLAYER_ALIAS_FIELDS = [
    FieldSpec("from", "Player identity", subtitle="MPRIS identity, e.g. com.github.th_ch.youtube_music"),
    FieldSpec("to", "Display name"),
]


# Shell setting -> Hyprland variables.lua key. Both are stored as fractions
# (0.1) in shell.json but as whole percentages (10) in variables.lua.
_PERCENT_SETTINGS = {
    "services.audioIncrement": "volumeStep",
    "services.maxVolume": "volumeMax",
}
_BRIGHTNESS_KEY = "services.brightnessIncrement"
_MISSING = object()


class ServicesBackend(ShellBackend):
    """Keep Caelestia's shell volume settings and Hyprland's keybinds in sync.

    The hardware volume keys are bound by ``keybinds.lua`` to
    ``wpctl set-volume ... vars.volumeStep%``.  They do not read Caelestia's
    ``services.audioIncrement`` directly, so writing only shell.json makes the
    setting look ineffective when using the laptop/media keys.
    """

    def get(self, key: str, kind: str | None = None, default=None):
        if key in _PERCENT_SETTINGS or key == _BRIGHTNESS_KEY:
            value = get_path(read_json(self.path, {}), key, _MISSING)
            if value is _MISSING:
                return default
            try:
                return round(float(value) * 100)
            except (TypeError, ValueError):
                return default
        return super().get(key, kind=kind, default=default)

    def set(self, key: str, value, label: str | None = None, record: bool = True) -> bool:
        is_percent = key in _PERCENT_SETTINGS or key == _BRIGHTNESS_KEY
        if not is_percent or not record:
            return super().set(key, value, label=label, record=record)

        try:
            shell_value = float(value) / 100.0
        except (TypeError, ValueError):
            return False

        var_key = _PERCENT_SETTINGS.get(key)
        old_shell = get_path(read_json(self.path, {}), key, None)
        if old_shell == shell_value:
            return True
        old_var = get_hypr_variable(var_key, None) if var_key else None

        if not super().set(key, shell_value, label=label, record=False):
            return False
        if var_key and not set_hypr_variable(var_key, int(value)):
            current = read_json(self.path, {})
            if old_shell is None:
                delete_path(current, key)
            else:
                set_path(current, key, copy.deepcopy(old_shell))
            atomic_write_json(self.path, current)
            if self.error_sink:
                self.error_sink(t("Could not update variables.lua"))
            return False

        def apply(shell_value_to_apply, var_value) -> None:
            current = read_json(self.path, {})
            if shell_value_to_apply is None:
                delete_path(current, key)
            else:
                set_path(current, key, copy.deepcopy(shell_value_to_apply))
            atomic_write_json(self.path, current)
            if var_key and var_value is not None:
                set_hypr_variable(var_key, var_value)
                hyprctl_reload()

        if record:
            HISTORY.push(
                label or f"{key} = {value}%",
                lambda: apply(old_shell, old_var),
                lambda: apply(shell_value, int(value)),
            )

        if var_key:
            hyprctl_reload()
        return True


class ServicesPage(SettingsPage):
    def __init__(self, main_window):
        backend = ServicesBackend(
            CAELESTIA_SHELL_JSON,
            error_sink=make_backend_error_toast(main_window),
        )
        super().__init__(main_window, SERVICES_SPEC, backend, custom_builders=[self._build_custom])
        self._apply_existing_volume_settings()

    def _apply_existing_volume_settings(self) -> None:
        """Apply values already stored in shell.json to Hyprland's keybinds.

        Older versions only wrote shell.json, so users who had configured the
        step in the app still had the hardware keys on the old value.  Only
        sync keys that are explicitly present, leaving a manually customised
        variables.lua alone when the app has no opinion about them.
        """
        data = read_json(CAELESTIA_SHELL_JSON, {})
        changed = False
        for key, var_key in _PERCENT_SETTINGS.items():
            raw = get_path(data, key, _MISSING)
            if raw is _MISSING:
                continue
            try:
                target = round(float(raw) * 100)
            except (TypeError, ValueError):
                continue
            if get_hypr_variable(var_key, None) != target:
                changed = bool(set_hypr_variable(var_key, target)) or changed
        if changed:
            hyprctl_reload()

    def _build_custom(self, page):
        add_object_list(
            page,
            self.backend,
            "services.playerAliases",
            PLAYER_ALIAS_DEFAULTS,
            PLAYER_ALIAS_FIELDS,
            "Player aliases",
            "Friendly names for MPRIS players.",
            title_key="to",
            new_item={"from": "", "to": "New player"},
        )
