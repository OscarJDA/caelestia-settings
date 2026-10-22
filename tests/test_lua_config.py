import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock gi and caelestia_core if running in environments without them installed
if "gi" not in sys.modules:
    gi_mock = MagicMock()
    sys.modules["gi"] = gi_mock
    sys.modules["gi.repository"] = MagicMock()
    sys.modules["gi.repository.Gtk"] = MagicMock()
    sys.modules["gi.repository.Adw"] = MagicMock()
    sys.modules["gi.repository.GLib"] = MagicMock()
    sys.modules["gi.repository.GdkPixbuf"] = MagicMock()

if "caelestia_core" not in sys.modules:
    core_mock = MagicMock()
    core_mock.parse_variables = lambda text: {}
    core_mock.resolve = lambda raw, v: raw
    core_mock.parse_monitors_conf = lambda text: ([], [])
    core_mock.parse_rules_conf = lambda text: []
    core_mock.find_conflicts = lambda rules: []
    sys.modules["caelestia_core"] = core_mock

from src import config
from src.pages import window_rules, keybinds, wallpaper


class LuaConfigTests(unittest.TestCase):
    def test_generate_rules_lua(self):
        rules = {
            "kitty": {
                "workspace": "1",
                "float": "true",
                "match_type": "class",
            },
            "gedit": {
                "workspace": "default",
                "float": "false",
                "match_type": "title",
            }
        }
        lines = window_rules._generate_rules_lua(rules)
        lua_output = "\n".join(lines)
        self.assertIn('hl.window_rule({ match = { class = "org.caelestia.settings" }, float = true, center = true })', lua_output)
        self.assertIn('match = { class = "kitty" }', lua_output)
        self.assertIn('workspace = "1"', lua_output)
        self.assertIn('float = true', lua_output)
        self.assertIn('match = { title = "gedit" }', lua_output)

    def test_parse_rules_lua(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_path = Path(tmpdir) / "rules.lua"
            rules_path.write_text(
                '-- Window rules\n'
                'hl.window_rule({\n'
                '    match = { class = "org.caelestia.settings" },\n'
                '    float = true,\n'
                '    center = true,\n'
                '})\n'
            )
            with patch.object(config, "CAELESTIA_RULES_LUA", rules_path), \
                 patch.object(config, "is_lua_mode", return_value=True):
                parsed = config.parse_rules_conf()
                self.assertEqual(len(parsed), 1)
                self.assertEqual(parsed[0]["match_type"], "class")
                self.assertEqual(parsed[0]["match_val"], "org.caelestia.settings")
                self.assertIn("float true", parsed[0]["rule"])

    def test_parse_monitors_lua(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mon_path = Path(tmpdir) / "monitors.lua"
            mon_path.write_text(
                'hl.monitor({\n'
                '    output = "DP-1",\n'
                '    mode = "2560x1440@165",\n'
                '    position = "0x0",\n'
                '    scale = 1.0,\n'
                '    bitdepth = 10,\n'
                '})\n'
                'hl.workspace_rule({\n'
                '    workspace = "1",\n'
                '    monitor = "DP-1",\n'
                '    default = true,\n'
                '})\n'
            )
            with patch.object(config, "CAELESTIA_MONITORS_LUA", mon_path), \
                 patch.object(config, "is_lua_mode", return_value=True):
                parsed = config.parse_monitors_conf()
                self.assertEqual(len(parsed["monitors"]), 1)
                mon = parsed["monitors"][0]
                self.assertEqual(mon["name"], "DP-1")
                self.assertEqual(mon["resolution"], "2560x1440@165")
                self.assertEqual(mon["position"], "0x0")
                self.assertEqual(len(parsed["workspaces"]), 1)
                self.assertEqual(parsed["workspaces"][0]["number"], 1)
                self.assertEqual(parsed["workspaces"][0]["monitor"], "DP-1")

    def test_keybinds_lua_save_and_parse(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / "user-keybinds.lua"
            user_hypr = Path(tmpdir) / "hypr-user.lua"
            with patch.object(keybinds, "CAELESTIA_KEYBINDS_LUA", kb_path), \
                 patch.object(keybinds, "is_lua_mode", return_value=True), \
                 patch.object(config, "CAELESTIA_HYPR_USER", user_hypr), \
                 patch.object(config, "CAELESTIA_CONFIG_DIR", Path(tmpdir)), \
                 patch.object(keybinds, "hyprctl_reload"):
                bind_data = {
                    "bind_type": "bind",
                    "modifier": "SUPER",
                    "key": "Return",
                    "dispatcher": "exec",
                    "argument": "kitty",
                    "comment": "Terminal",
                }
                keybinds.save_keybind(bind_data)
                self.assertTrue(kb_path.exists())
                content = kb_path.read_text()
                self.assertIn('hl.bind("SUPER + Return", hl.dsp.exec_cmd("kitty"))', content)

                parsed = keybinds.parse_keybinds()
                self.assertTrue(any(b["key_raw"] == "Return" and b["argument"] == "kitty" for b in parsed))

    def test_wallpaper_shell_json_and_lua_autostart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            shell_json_path = Path(tmpdir) / "shell.json"
            hypr_user_path = Path(tmpdir) / "hypr-user.lua"
            shell_json_path.write_text(
                '{\n'
                '    "paths": { "wallpaperDir": "~/Pictures/Wallpapers" },\n'
                '    "background": {\n'
                '        "desktopClock": {\n'
                '            "enabled": true,\n'
                '            "position": "bottom-right",\n'
                '            "scale": 1.2\n'
                '        }\n'
                '    }\n'
                '}\n'
            )
            with patch.object(wallpaper, "CAELESTIA_SHELL_JSON", shell_json_path), \
                 patch.object(wallpaper, "CAELESTIA_HYPR_USER", hypr_user_path), \
                 patch.object(wallpaper, "is_lua_mode", return_value=True):
                # Verify expanded path
                wall_dir = wallpaper._get_image_dir()
                self.assertNotIn("~", str(wall_dir))
                self.assertTrue(str(wall_dir).endswith("Wallpapers"))

                # Verify clock settings read
                clk = wallpaper._get_clock_settings()
                self.assertTrue(clk["enabled"])
                self.assertEqual(clk["position"], "bottom-right")
                self.assertEqual(clk["scale"], 1.2)

                # Verify mpvpaper autostart in Lua mode
                test_video = Path("/home/user/Videos/Wallpaper/loop.mp4")
                wallpaper._write_mpvpaper_autostart(test_video)
                self.assertTrue(hypr_user_path.exists())
                content = hypr_user_path.read_text()
                self.assertIn("hl.exec_cmd(", content)
                self.assertIn("mpvpaper", content)
                self.assertIn("-- caelestia-settings: video-wallpaper", content)

                # Test removing autostart
                wallpaper._write_mpvpaper_autostart(None)
                content = hypr_user_path.read_text()
                self.assertNotIn("mpvpaper", content)


if __name__ == "__main__":
    unittest.main()
