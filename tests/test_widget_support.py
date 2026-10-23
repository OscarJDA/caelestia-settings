"""Tests for the shell-side widget support installer."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import widget_support  # noqa: E402

SHELL_QML = """import "modules/background"

ShellRoot {
    Background {}
    Drawers {}
}
"""

SHELL_QML_CRLF = SHELL_QML.replace("\n", "\r\n")


class WidgetSupportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.shell = Path(self._tmp.name) / "caelestia"
        self.module = self.shell / "modules" / "background"
        self.module.mkdir(parents=True)
        self.write_shell(SHELL_QML)
        self._env = patch.dict(os.environ, {widget_support.SHELL_DIR_ENV: str(self.shell)})
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)

    def write_shell(self, text: str) -> None:
        with (self.shell / "shell.qml").open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read_shell(self) -> str:
        with (self.shell / "shell.qml").open("r", encoding="utf-8", newline="") as handle:
            return handle.read()


class DetectionTests(WidgetSupportTestCase):
    def test_missing_files_are_not_installed(self):
        self.assertFalse(widget_support.is_installed())

    def test_files_without_entry_are_not_installed(self):
        for name in ("DesktopWidgets.qml", "WidgetCatalog.js", "WidgetCard.qml"):
            (self.module / name).write_text("// stub\n", encoding="utf-8")
        self.assertFalse(widget_support.is_installed())

    def test_complete_installation_is_detected(self):
        widget_support.install()
        self.assertTrue(widget_support.is_installed())

    def test_shell_dir_can_be_overridden(self):
        self.assertEqual(widget_support.shell_dir(), self.shell)


class InstallTests(WidgetSupportTestCase):
    def test_install_copies_bundle_and_patches_shell(self):
        result = widget_support.install()

        self.assertTrue(result.patched)
        self.assertTrue((self.module / "DesktopWidgets.qml").is_file())
        self.assertTrue((self.module / "WidgetClock.qml").is_file())
        self.assertIn("DesktopWidgets {}", self.read_shell())
        self.assertTrue((result.backup / "shell.qml").is_file())

    def test_entry_follows_background(self):
        widget_support.install()
        lines = self.read_shell().splitlines()
        self.assertEqual(lines.index("    Background {}") + 1, lines.index("    DesktopWidgets {}"))

    def test_install_is_idempotent(self):
        widget_support.install()
        before = self.read_shell()

        result = widget_support.install()

        self.assertFalse(result.patched)
        self.assertEqual(self.read_shell(), before)
        self.assertEqual(before.count("DesktopWidgets {}"), 1)

    def test_crlf_is_preserved(self):
        self.write_shell(SHELL_QML_CRLF)
        widget_support.install()

        raw = (self.shell / "shell.qml").read_bytes()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertIn(b"    DesktopWidgets {}\r\n", raw)

    def test_replaced_widgets_are_backed_up(self):
        (self.module / "WidgetClock.qml").write_text("// local edit\n", encoding="utf-8")

        result = widget_support.install()

        backup = (result.backup / "WidgetClock.qml").read_text(encoding="utf-8")
        self.assertEqual(backup, "// local edit\n")

    def test_falls_back_to_drawers_when_background_is_missing(self):
        self.write_shell('ShellRoot {\n    Drawers {}\n}\n')
        widget_support.install()
        lines = self.read_shell().splitlines()
        self.assertEqual(lines.index("    Drawers {}") - 1, lines.index("    DesktopWidgets {}"))

    def test_missing_shell_qml_raises(self):
        (self.shell / "shell.qml").unlink()
        with self.assertRaises(widget_support.WidgetSupportError):
            widget_support.install()

    def test_missing_module_dir_raises(self):
        (self.module).rmdir()
        with self.assertRaises(widget_support.WidgetSupportError):
            widget_support.install()

    def test_no_entry_point_raises(self):
        self.write_shell("ShellRoot {}\n")
        with self.assertRaises(widget_support.WidgetSupportError):
            widget_support.install()

    def test_failure_rolls_back_shell_and_files(self):
        (self.module / "WidgetClock.qml").write_text("// local edit\n", encoding="utf-8")
        before = self.read_shell()

        with patch.object(widget_support, "_write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                widget_support.install()

        self.assertEqual(self.read_shell(), before)
        self.assertEqual(
            (self.module / "WidgetClock.qml").read_text(encoding="utf-8"),
            "// local edit\n",
        )
        self.assertFalse((self.module / "DesktopWidgets.qml").exists())


class BundleTests(unittest.TestCase):
    def test_bundle_contains_required_files(self):
        names = set(widget_support.bundle_files())
        self.assertTrue({"DesktopWidgets.qml", "WidgetCatalog.js", "WidgetCard.qml"} <= names)
        self.assertIn("WidgetClock.qml", names)
        self.assertNotIn("SOURCE.md", names)


if __name__ == "__main__":
    unittest.main()
