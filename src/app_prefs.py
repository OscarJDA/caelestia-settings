"""Application-level preferences (independent of Caelestia/Hyprland)."""

from __future__ import annotations

from pathlib import Path

from src.safe_io import atomic_write_json, read_json

APP_PREFS_FILE = Path.home() / ".config" / "caelestia-settings" / "app.json"

LANGUAGE_CHOICES: tuple[tuple[str, str], ...] = (
    ("auto", "Automatic (system)"),
    ("en", "English"),
    ("es_MX", "Español (México)"),
    ("de", "Deutsch"),
)
_VALID_LANGUAGES = {code for code, _label in LANGUAGE_CHOICES}


def get_language_preference() -> str:
    value = read_json(APP_PREFS_FILE, {}).get("language", "auto")
    return value if value in _VALID_LANGUAGES else "auto"


def set_language_preference(value: str) -> None:
    if value not in _VALID_LANGUAGES:
        value = "auto"
    data = read_json(APP_PREFS_FILE, {})
    data["language"] = value
    atomic_write_json(APP_PREFS_FILE, data)
