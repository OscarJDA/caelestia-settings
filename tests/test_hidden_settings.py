import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The real extension is built/installed in the full app environment.  The
# tests only exercise pure Python paths, so provide a stub when it is absent
# (as on the CI runner).
try:
    import caelestia_core  # noqa: F401
except ImportError:
    from unittest.mock import MagicMock

    sys.modules["caelestia_core"] = MagicMock()

import src.hypr_vars as hypr_vars
from src.pages import keybinds, services
from src.safe_io import read_json
from src.settings_schema import APPEARANCE_SPEC, BAR_SPEC, TYPOGRAPHY_SPEC, Expander, Option


def _walk(rows):
    for row in rows:
        if isinstance(row, Option):
            yield row
        elif isinstance(row, Expander):
            yield from _walk(row.rows)


def _option(spec, key):
    return next(
        option
        for group in spec.groups
        for option in _walk(group.rows)
        if option.key == key
    )


class SchemaDefaultTests(unittest.TestCase):
    def test_bar_workspace_label_uses_caelestia_default(self):
        self.assertEqual(_option(BAR_SPEC, "bar.workspaces.label").default, "\uf444  ")

    def test_transparency_is_off_by_default(self):
        self.assertFalse(_option(APPEARANCE_SPEC, "appearance.transparency.enabled").default)

    def test_font_italics_default_to_false(self):
        for group in TYPOGRAPHY_SPEC.groups:
            for option in _walk(group.rows):
                if option.key.endswith(".italic"):
                    self.assertFalse(option.default, option.key)


class HyprVarsTests(unittest.TestCase):
    def test_get_set_and_preserve_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "variables.lua"
            path.write_text(
                'return {\n    terminal = "foot",\n    volumeStep = 10,\n}\n'
            )
            with patch.object(hypr_vars, "HYPR_VARIABLES", path):
                self.assertEqual(hypr_vars.get_hypr_variable("terminal"), "foot")
                self.assertEqual(hypr_vars.get_hypr_variable("volumeStep"), 10)
                self.assertTrue(hypr_vars.set_hypr_variable("browser", "firefox"))
                self.assertTrue(hypr_vars.set_hypr_variable("volumeStep", 5))
                self.assertEqual(hypr_vars.get_hypr_variable("browser"), "firefox")
                self.assertEqual(hypr_vars.get_hypr_variable("volumeStep"), 5)
                self.assertIn('terminal = "foot"', path.read_text())

    def test_setting_same_value_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "variables.lua"
            path.write_text('return {\n    browser = "firefox",\n}\n')
            with patch.object(hypr_vars, "HYPR_VARIABLES", path):
                self.assertTrue(hypr_vars.set_hypr_variable("browser", "firefox"))


class ServicesBackendTests(unittest.TestCase):
    def test_percent_ui_values_sync_to_shell_and_hyprland(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shell = tmp_path / "shell.json"
            shell.write_text(
                json.dumps(
                    {
                        "services": {
                            "audioIncrement": 0.1,
                            "brightnessIncrement": 0.1,
                            "maxVolume": 1.0,
                        }
                    }
                )
            )
            variables = tmp_path / "variables.lua"
            variables.write_text(
                "return {\n    volumeStep = 10,\n    volumeMax = 100,\n}\n"
            )
            with patch.object(hypr_vars, "HYPR_VARIABLES", variables), patch.object(
                services, "hyprctl_reload", lambda: None
            ):
                backend = services.ServicesBackend(shell)
                self.assertEqual(backend.get("services.audioIncrement"), 10)
                self.assertEqual(backend.get("services.brightnessIncrement"), 10)
                self.assertEqual(backend.get("services.maxVolume"), 100)

                self.assertTrue(backend.set("services.audioIncrement", 5))
                self.assertAlmostEqual(read_json(shell)["services"]["audioIncrement"], 0.05)
                self.assertEqual(hypr_vars.get_hypr_variable("volumeStep"), 5)

                self.assertTrue(backend.set("services.maxVolume", 150))
                self.assertAlmostEqual(read_json(shell)["services"]["maxVolume"], 1.5)
                self.assertEqual(hypr_vars.get_hypr_variable("volumeMax"), 150)

                self.assertTrue(backend.set("services.brightnessIncrement", 20))
                self.assertAlmostEqual(
                    read_json(shell)["services"]["brightnessIncrement"], 0.2
                )


class KeybindLuaActionTests(unittest.TestCase):
    def test_common_dispatchers_use_lua_api(self):
        cases = {
            "exec": 'hl.dsp.exec_cmd("kitty")',
            "workspace": 'hl.dsp.focus({ workspace = "2" })',
            "movetoworkspace": 'hl.dsp.window.move({ workspace = "3" })',
            "killactive": "hl.dsp.window.close()",
            "togglefloating": 'hl.dsp.window.float({ action = "toggle" })',
            "fullscreen": 'hl.dsp.window.fullscreen({ mode = "maximized" })',
            "movefocus": 'hl.dsp.focus({ direction = "left" })',
            "focuswindow": 'hl.dsp.focus({ window = "class:kitty" })',
            "layoutmsg": 'hl.dsp.layout("fit active")',
            "global": 'hl.dsp.global("caelestia:launcher")',
        }
        args = {
            "exec": "kitty",
            "workspace": "2",
            "movetoworkspace": "3",
            "fullscreen": "1",
            "movefocus": "left",
            "focuswindow": "class:kitty",
            "layoutmsg": "fit active",
            "global": "caelestia:launcher",
        }
        for dispatcher, expected in cases.items():
            self.assertEqual(
                keybinds._lua_action(dispatcher, args.get(dispatcher, "")),
                expected,
                dispatcher,
            )

    def test_unsupported_dispatcher_is_reported(self):
        self.assertIsNone(keybinds._lua_action("fakefullscreen", ""))
        self.assertIsNone(keybinds._lua_action("workspaceopt", "allfloat"))


if __name__ == "__main__":
    unittest.main()
