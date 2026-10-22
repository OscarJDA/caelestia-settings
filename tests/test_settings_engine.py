import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hypr_options_catalog import OPTIONS
from src import settings_core
from src.hypr_settings import HyprBackend
from src.rules_core import (
    match_rules_against_clients,
    render_conf_rule,
    render_lua_rule,
    rule_matches_client,
)
from src.safe_io import History, atomic_write_text, read_json
from src.settings_schema import (
    APPEARANCE_SPEC,
    BAR_SPEC,
    DASHBOARD_SPEC,
    HYPR_ANIMATIONS_SPEC,
    HYPR_DECORATION_SPEC,
    HYPR_GENERAL_SPEC,
    HYPR_GESTURES_SPEC,
    HYPR_INPUT_SPEC,
    LAUNCHER_SPEC,
    LOCK_SPEC,
    LOGIN_THEME_SPEC,
    MONITOR_OVERRIDE_SPEC,
    NOTIFICATIONS_SPEC,
    POWER_SPEC,
    SERVICES_SPEC,
    SIDEBAR_UTILITIES_SPEC,
    TYPOGRAPHY_SPEC,
    Expander,
    Option,
)


class NestedPathTests(unittest.TestCase):
    def test_get_set_delete(self):
        data = {}
        settings_core.set_path(data, "appearance.transparency.enabled", True)
        self.assertEqual(data["appearance"]["transparency"]["enabled"], True)
        self.assertTrue(settings_core.get_path(data, "appearance.transparency.enabled"))
        self.assertIsNone(settings_core.get_path(data, "appearance.missing", None))

        self.assertTrue(settings_core.delete_path(data, "appearance.transparency.enabled"))
        self.assertNotIn("enabled", data["appearance"]["transparency"])
        self.assertFalse(settings_core.delete_path(data, "appearance.transparency.enabled"))

    def test_deep_merge_does_not_mutate_inputs(self):
        base = {"a": {"b": 1}, "c": 2}
        overlay = {"a": {"d": 3}}
        merged = settings_core.deep_merge(base, overlay)
        self.assertEqual(merged, {"a": {"b": 1, "d": 3}, "c": 2})
        self.assertEqual(base, {"a": {"b": 1}, "c": 2})


class LuaRenderingTests(unittest.TestCase):
    def test_hypr_option_tree_handles_nested_and_hyphenated_keys(self):
        tree = settings_core.hypr_option_to_tree("input:touchpad:tap-to-click", True)
        self.assertEqual(tree, {"input": {"touchpad": {"tap-to-click": True}}})

    def test_lua_render_normalizes_hyphenated_keys(self):
        tree = settings_core.hypr_option_to_tree("input:touchpad:tap-to-click", True)
        text = settings_core.render_lua_config(tree)
        self.assertIn("tap_to_click = true", text)
        self.assertNotIn("tap-to-click", text)
        self.assertTrue(text.startswith("hl.config({"))

    def test_lua_strings_are_escaped_without_json_unicode_escapes(self):
        self.assertEqual(settings_core.lua_quote('a"b'), '"a\\"b"')
        self.assertEqual(settings_core.lua_quote("a\nb"), '"a\\nb"')
        self.assertEqual(settings_core.lua_quote("ñ"), '"ñ"')
        self.assertNotIn("\\u", settings_core.lua_quote("ñ"))

    def test_empty_tree_is_valid_lua(self):
        text = settings_core.render_lua_config({})
        self.assertIn("No overrides", text)
        self.assertNotIn("hl.config", text)

    def test_conf_render_keeps_hyphenated_option_names(self):
        tree = settings_core.hypr_option_to_tree("input:touchpad:tap-to-click", False)
        text = settings_core.render_conf_overrides(tree)
        self.assertIn("input:touchpad:tap-to-click = false", text)


class LuaExtrasTests(unittest.TestCase):
    def test_render_curve_animation_and_gesture(self):
        extras = {
            "curves": {"standard": {"type": "bezier", "points": [[0.2, 0.0], [0.0, 1.0]]}},
            "animations": {"windowsIn": {"enabled": True, "speed": 5, "bezier": "standard", "style": "slide"}},
            "gestures": [{"fingers": 3, "direction": "horizontal", "action": "workspace"}],
        }
        text = settings_core.render_lua_extras(extras)
        self.assertIn('hl.curve("standard"', text)
        self.assertIn('leaf = "windowsIn"', text)
        self.assertIn('hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })', text)

    def test_render_conf_extras(self):
        extras = {
            "curves": {"standard": {"points": [[0.2, 0.0], [0.0, 1.0]]}},
            "animations": {"windowsIn": {"enabled": False, "speed": 5, "bezier": "standard", "style": ""}},
        }
        text = settings_core.render_conf_extras(extras)
        self.assertIn("bezier = standard, 0.2, 0.0, 0.0, 1.0", text)
        self.assertIn("animation = windowsIn, 0, 5.0, standard,", text)

    def test_empty_extras_is_empty(self):
        self.assertEqual(settings_core.render_lua_extras({}), "")


class RulesCoreTests(unittest.TestCase):
    def test_lua_and_conf_rendering(self):
        rule = {
            "match_field": "class",
            "match_value": "kitty",
            "float": True,
            "no_blur": True,
            "size": "800 600",
            "opacity": "0.9 override",
        }
        lua = render_lua_rule(rule)
        self.assertIn('match = { class = "kitty" }', lua)
        self.assertIn("float = true", lua)
        self.assertIn('size = "800 600"', lua)
        conf = render_conf_rule(rule)
        self.assertIn("windowrule = float true, match:class kitty", conf)
        self.assertIn("windowrule = noblur true, match:class kitty", conf)
        self.assertIn("windowrule = opacity 0.9 override, match:class kitty", conf)

    def test_xwayland_match(self):
        rule = {"match_field": "xwayland", "match_value": "true", "pin": True}
        self.assertIn("xwayland = true", render_lua_rule(rule))
        self.assertIn("windowrule = pin true, match:xwayland 1", render_conf_rule(rule))

    def test_rule_matching(self):
        clients = [
            {"class": "kitty", "title": "Terminal", "xwayland": False, "tags": []},
            {"class": "steam_app_123", "title": "Game", "xwayland": True, "tags": ["game"]},
        ]
        self.assertTrue(rule_matches_client({"match_field": "class", "match_value": "kit"}, clients[0]))
        self.assertFalse(rule_matches_client({"match_field": "xwayland", "match_value": "true"}, clients[0]))
        self.assertTrue(rule_matches_client({"match_field": "tag", "match_value": "game"}, clients[1]))
        results = match_rules_against_clients(
            [{"match_field": "class", "match_value": "kitty"}], clients
        )
        self.assertEqual(len(results[0][1]), 1)



class HyprValueParsingTests(unittest.TestCase):
    def test_parse_types(self):
        self.assertIs(settings_core.parse_hypr_option({"bool": True}), True)
        self.assertEqual(settings_core.parse_hypr_option({"int": 5}), 5)
        self.assertEqual(settings_core.parse_hypr_option({"float": 0.3}), 0.3)
        self.assertEqual(settings_core.parse_hypr_option({"str": "[[EMPTY]]"}), "")
        self.assertEqual(settings_core.parse_hypr_option({"str": "scrolling"}), "scrolling")

    def test_css_gap_with_kind_hint(self):
        raw = {"css": "5 5 5 5"}
        self.assertEqual(settings_core.parse_hypr_option(raw, "int"), 5)
        self.assertEqual(settings_core.parse_hypr_option(raw, "float"), 5.0)


class SafeIoTests(unittest.TestCase):
    def test_atomic_write_and_read_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "shell.json"
            self.assertTrue(atomic_write_text(path, '{"a": 1}'))
            self.assertFalse(atomic_write_text(path, '{"a": 1}'))
            self.assertEqual(read_json(path), {"a": 1})
            self.assertEqual(path.read_text(), '{"a": 1}')

    def test_history_undo_redo(self):
        history = History()
        state = {"value": 0}

        def write(value):
            def apply():
                state["value"] = value

            return apply

        history.push("set 1", write(0), write(1))
        state["value"] = 1
        self.assertTrue(history.can_undo)
        self.assertEqual(history.undo(), "set 1")
        self.assertEqual(state["value"], 0)
        self.assertTrue(history.can_redo)
        self.assertEqual(history.redo(), "set 1")
        self.assertEqual(state["value"], 1)


class HyprOverrideTreeTests(unittest.TestCase):
    def test_set_and_remove_nested_value(self):
        tree = HyprBackend._set_in_tree({}, "input:touchpad:tap-to-click", True)
        self.assertEqual(tree, {"input": {"touchpad": {"tap-to-click": True}}})
        tree = HyprBackend._set_in_tree(tree, "input:touchpad:tap-to-click", "")
        self.assertEqual(tree, {})

    def test_empty_string_can_be_a_value(self):
        tree = HyprBackend._set_in_tree({}, "input:kb_variant", ",intl")
        tree = HyprBackend._set_in_tree(tree, "input:kb_variant", "", empty_is_value=True)
        self.assertEqual(tree, {"input": {"kb_variant": ""}})
        tree = HyprBackend._set_in_tree(tree, "input:accel_profile", "")
        self.assertNotIn("accel_profile", tree.get("input", {}))

    def test_remove_prunes_only_empty_parents(self):
        tree = {"input": {"touchpad": {"natural_scroll": True}, "kb_layout": "us"}}
        tree = HyprBackend._set_in_tree(tree, "input:touchpad:natural_scroll", "")
        self.assertEqual(tree, {"input": {"kb_layout": "us"}})
        tree = HyprBackend._set_in_tree(tree, "input:kb_layout", "")
        self.assertEqual(tree, {})


class SchemaTests(unittest.TestCase):
    SPECS = (
        APPEARANCE_SPEC,
        TYPOGRAPHY_SPEC,
        BAR_SPEC,
        LAUNCHER_SPEC,
        DASHBOARD_SPEC,
        SIDEBAR_UTILITIES_SPEC,
        NOTIFICATIONS_SPEC,
        LOCK_SPEC,
        POWER_SPEC,
        SERVICES_SPEC,
        MONITOR_OVERRIDE_SPEC,
        LOGIN_THEME_SPEC,
        HYPR_GENERAL_SPEC,
        HYPR_DECORATION_SPEC,
        HYPR_INPUT_SPEC,
        HYPR_ANIMATIONS_SPEC,
        HYPR_GESTURES_SPEC,
    )

    def _walk_options(self, rows):
        for row in rows:
            if isinstance(row, Option):
                yield row
            elif isinstance(row, Expander):
                yield from self._walk_options(row.rows)

    def test_option_kinds_and_defaults(self):
        valid_kinds = {"bool", "int", "float", "enum", "string", "font"}
        for spec in self.SPECS:
            seen: set[str] = set()
            for group in spec.groups:
                for option in self._walk_options(group.rows):
                    self.assertIn(option.kind, valid_kinds, option.key)
                    self.assertNotIn(option.key, seen, f"duplicate key in {spec.page_id}")
                    seen.add(option.key)
                    if option.kind in ("int", "float"):
                        self.assertLessEqual(option.minimum, option.maximum, option.key)
                        self.assertLessEqual(option.minimum, option.default, option.key)
                        self.assertLessEqual(option.default, option.maximum, option.key)
                    if option.kind == "enum":
                        values = [value for value, _label in option.choices]
                        self.assertIn(option.default, values, option.key)

    def test_page_ids_are_unique(self):
        page_ids = [spec.page_id for spec in self.SPECS]
        self.assertEqual(len(page_ids), len(set(page_ids)))

    def test_hypr_option_catalogue(self):
        names = [name for name, _description, _type in OPTIONS]
        self.assertGreater(len(names), 300)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("general:layout", names)
        self.assertIn("decoration:blur:enabled", names)

    def test_lyrics_backend_uses_caelestia_enum_values(self):
        option = next(
            option
            for group in SERVICES_SPEC.groups
            for option in self._walk_options(group.rows)
            if option.key == "services.lyricsBackend"
        )
        values = [value for value, _label in option.choices]
        self.assertIn("LRCLIB", values)
        self.assertNotIn("LRCLib", values)


if __name__ == "__main__":
    unittest.main()
