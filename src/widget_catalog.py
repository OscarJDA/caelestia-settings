"""Catalogue of desktop widgets rendered by the Caelestia shell fork.

Keep this in sync with ``shell/modules/background/WidgetCatalog.js``.  The
shell merges unknown/missing options with its own defaults, so only the option
metadata used to build the settings UI needs to live here.
"""

from __future__ import annotations

CORNERS = (
    ("top-left", "Top left"),
    ("top-center", "Top center"),
    ("top-right", "Top right"),
    ("middle-left", "Middle left"),
    ("middle-center", "Middle center"),
    ("middle-right", "Middle right"),
    ("bottom-left", "Bottom left"),
    ("bottom-center", "Bottom center"),
    ("bottom-right", "Bottom right"),
)

CARD_STYLES = (
    ("material", "Material card"),
    ("glass", "Frosted glass"),
    ("minimal", "Minimal"),
)

ACCENTS = (
    ("auto", "Automatic"),
    ("primary", "Primary"),
    ("secondary", "Secondary"),
    ("tertiary", "Tertiary"),
    ("error", "Error"),
)


def _bool(label: str, default: bool) -> dict:
    return {"label": label, "kind": "bool", "default": default}


def _int(label: str, default: int, minimum: int, maximum: int, step: int = 1) -> dict:
    return {
        "label": label,
        "kind": "int",
        "default": default,
        "min": minimum,
        "max": maximum,
        "step": step,
    }


def _float(label: str, default: float, minimum: float, maximum: float, step: float, digits: int = 2) -> dict:
    return {
        "label": label,
        "kind": "float",
        "default": default,
        "min": minimum,
        "max": maximum,
        "step": step,
        "digits": digits,
    }


def _choice(label: str, default: str, choices: tuple[tuple[str, str], ...]) -> dict:
    return {"label": label, "kind": "choice", "default": default, "choices": choices}


def _text(label: str, default: str, placeholder: str = "") -> dict:
    return {"label": label, "kind": "text", "default": default, "placeholder": placeholder}


_TIME_FORMATS = (
    ("system", "System"),
    ("12h", "12-hour"),
    ("24h", "24-hour"),
)

WIDGETS: dict[str, dict] = {
    "clock": {
        "name": "Clock",
        "icon": "schedule",
        "width": 300,
        "corner": "top-center",
        "options": {
            "showDate": _bool("Show date", True),
            "showWeekday": _bool("Show weekday", True),
            "showSeconds": _bool("Show seconds", False),
            "dateFormat": _choice(
                "Date format",
                "long",
                (("long", "Long"), ("short", "Short"), ("iso", "ISO")),
            ),
            "format": _choice("Time format", "system", _TIME_FORMATS),
        },
    },
    "worldclock": {
        "name": "World clock",
        "icon": "public",
        "width": 280,
        "corner": "middle-left",
        "options": {
            "cities": _text(
                "Cities",
                "Tokyo:+9,London:+0,New York:-5",
                "Tokyo:+9, London:+0, New York:-5",
            ),
            "format": _choice("Time format", "system", _TIME_FORMATS),
            "showOffset": _bool("Show UTC offset", True),
        },
    },
    "moon": {
        "name": "Moon phase",
        "icon": "dark_mode",
        "width": 260,
        "corner": "middle-left",
        "options": {
            "hemisphere": _choice(
                "Hemisphere",
                "north",
                (("north", "Northern"), ("south", "Southern")),
            ),
            "showName": _bool("Show phase name", True),
            "showIllumination": _bool("Show illumination", True),
        },
    },
    "calendar": {
        "name": "Calendar",
        "icon": "calendar_month",
        "width": 300,
        "corner": "bottom-center",
        "options": {
            "weekNumbers": _bool("Week numbers", False),
            "showWeekdays": _bool("Show weekday names", True),
            "startOfWeek": _choice(
                "First day of week",
                "locale",
                (("locale", "Locale"), ("monday", "Monday"), ("sunday", "Sunday")),
            ),
        },
    },
    "agenda": {
        "name": "Agenda",
        "icon": "event_note",
        "width": 320,
        "corner": "middle-right",
        "options": {
            "path": _text(
                "Calendar file",
                "~/.config/caelestia-settings/agenda.ics",
                "~/.config/caelestia-settings/agenda.ics",
            ),
            "maxEvents": _int("Events shown", 5, 1, 12),
            "daysAhead": _int("Days ahead", 14, 1, 365),
            "showLocation": _bool("Show location", True),
        },
    },
    "weather": {
        "name": "Weather",
        "icon": "cloud",
        "width": 300,
        "corner": "bottom-right",
        "options": {
            "showFeelsLike": _bool("Show feels-like temperature", True),
            "showHumidity": _bool("Show humidity", True),
            "showWind": _bool("Show wind", True),
            "showSun": _bool("Show sunrise", True),
            "showCity": _bool("Show city", True),
        },
    },
    "forecast": {
        "name": "Forecast",
        "icon": "thermostat",
        "width": 320,
        "corner": "bottom-right",
        "options": {
            "mode": _choice(
                "Forecast",
                "hourly",
                (("hourly", "Hourly"), ("daily", "Daily"), ("both", "Both")),
            ),
            "count": _int("Entries shown", 6, 1, 12),
            "showPrecip": _bool("Show precipitation chance", True),
        },
    },
    "airquality": {
        "name": "Air quality",
        "icon": "air",
        "width": 300,
        "corner": "bottom-right",
        "options": {
            "pollutant": _choice(
                "Index",
                "european",
                (("european", "European AQI"), ("us", "US AQI")),
            ),
            "showPm": _bool("Show particulate matter", True),
        },
    },
    "system": {
        "name": "System monitor",
        "icon": "monitor_heart",
        "width": 300,
        "corner": "top-right",
        "options": {
            "showCpu": _bool("Show CPU", True),
            "showGpu": _bool("Show GPU", True),
            "showMemory": _bool("Show memory", True),
            "showStorage": _bool("Show storage", True),
            "showNetwork": _bool("Show network", True),
            "showBars": _bool("Show usage bars", True),
            "showTemps": _bool("Show temperatures", True),
            "compact": _bool("Compact (hide details)", False),
        },
    },
    "storage": {
        "name": "Storage",
        "icon": "hard_drive",
        "width": 300,
        "corner": "middle-right",
        "options": {
            "maxDisks": _int("Disks shown", 4, 1, 8),
            "showBars": _bool("Show usage bars", True),
            "showFree": _bool("Show free space", True),
        },
    },
    "network": {
        "name": "Network",
        "icon": "swap_vert",
        "width": 320,
        "corner": "top-right",
        "options": {
            "showSparkline": _bool("Show traffic graph", True),
            "showTotals": _bool("Show session totals", True),
            "showSsid": _bool("Show Wi-Fi network", True),
            "showVpn": _bool("Show VPN status", True),
        },
    },
    "battery": {
        "name": "Battery",
        "icon": "battery_full",
        "width": 280,
        "corner": "bottom-center",
        "options": {
            "showTime": _bool("Show remaining time", True),
            "showHealth": _bool("Show battery health", False),
            "showProfile": _bool("Show power profile", True),
            "lowThreshold": _int("Low battery threshold (%)", 20, 0, 100, 5),
        },
    },
    "sensors": {
        "name": "Sensors",
        "icon": "device_thermostat",
        "width": 300,
        "corner": "middle-right",
        "options": {
            "maxItems": _int("Readings shown", 4, 1, 20),
            "showTemps": _bool("Show temperatures", True),
            "showFans": _bool("Show fan speeds", True),
        },
    },
    "processes": {
        "name": "Top processes",
        "icon": "list_alt",
        "width": 320,
        "corner": "middle-right",
        "options": {
            "count": _int("Processes shown", 5, 1, 20),
            "sortBy": _choice(
                "Sort by",
                "cpu",
                (("cpu", "CPU usage"), ("memory", "Memory usage")),
            ),
        },
    },
    "sysinfo": {
        "name": "System information",
        "icon": "info",
        "width": 300,
        "corner": "middle-left",
        "options": {
            "showHost": _bool("Show hostname", True),
            "showDevice": _bool("Show device model", True),
            "showKernel": _bool("Show kernel", True),
            "showUptime": _bool("Show uptime", True),
            "showCpu": _bool("Show CPU model", True),
            "showGpu": _bool("Show GPU model", False),
            "showWm": _bool("Show session", True),
        },
    },
    "media": {
        "name": "Media player",
        "icon": "music_note",
        "width": 340,
        "corner": "bottom-left",
        "options": {
            "showArt": _bool("Show album art", True),
            "showAlbum": _bool("Show album", True),
            "showControls": _bool("Show playback controls", True),
            "showProgress": _bool("Show progress bar", True),
            "hideWhenStopped": _bool("Hide when nothing is playing", False),
        },
    },
    "lyrics": {
        "name": "Lyrics",
        "icon": "lyrics",
        "width": 360,
        "corner": "bottom-left",
        "options": {
            "lines": _int("Lines shown", 3, 1, 9),
            "centered": _bool("Centre text", True),
            "showTitle": _bool("Show track title", False),
        },
    },
    "visualiser": {
        "name": "Audio visualiser",
        "icon": "graphic_eq",
        "width": 320,
        "corner": "bottom-center",
        "options": {
            "widthScale": _float("Horizontal scale", 1.0, 0.5, 4.0, 0.25),
            "heightScale": _float("Vertical scale", 1.0, 0.5, 4.0, 0.25),
            "style": _choice(
                "Style",
                "bars",
                (("bars", "Bars"), ("curve", "Curve"), ("pulse", "Pulse")),
            ),
            "colorMode": _choice(
                "Colour source",
                "artwork",
                (("artwork", "Album art"), ("accent", "Theme accent")),
            ),
            "bars": _int("Bars", 48, 8, 128),
            "mirror": _bool("Mirror bars", True),
            "showWhenIdle": _bool("Show when idle", False),
        },
    },
    "quickactions": {
        "name": "Quick actions",
        "icon": "bolt",
        "width": 300,
        "corner": "middle-right",
        "options": {
            "actions": _text(
                "Actions",
                "lock,suspend,reboot,shutdown,screenshot,record,dnd",
                "lock,suspend,reboot,shutdown,screenshot,record,dnd",
            ),
            "columns": _int("Columns", 4, 2, 6),
            "confirm": _bool("Ask before destructive actions", True),
        },
    },
    "launcher": {
        "name": "App launcher",
        "icon": "apps",
        "width": 320,
        "corner": "middle-left",
        "options": {
            "apps": _text("Applications", "", "Empty = alphabetical list"),
            "columns": _int("Columns", 4, 2, 8),
            "showNames": _bool("Show application names", False),
        },
    },
    "notes": {
        "name": "Notes",
        "icon": "sticky_note_2",
        "width": 300,
        "corner": "middle-left",
        "options": {
            "path": _text(
                "Notes file",
                "~/.config/caelestia-settings/notes.txt",
                "~/.config/caelestia-settings/notes.txt",
            ),
            "maxLines": _int("Lines shown", 6, 1, 40),
            "openOnClick": _bool("Open editor when clicked", True),
        },
    },
    "pomodoro": {
        "name": "Pomodoro",
        "icon": "timer",
        "width": 260,
        "corner": "middle-left",
        "options": {
            "workMinutes": _int("Focus length (minutes)", 25, 1, 180),
            "shortBreakMinutes": _int("Short break (minutes)", 5, 1, 60),
            "longBreakMinutes": _int("Long break (minutes)", 15, 1, 120),
            "longBreakEvery": _int("Long break every N sessions", 4, 1, 12),
            "autoStartBreaks": _bool("Start breaks automatically", False),
        },
    },
    "stopwatch": {
        "name": "Stopwatch",
        "icon": "av_timer",
        "width": 260,
        "corner": "middle-left",
        "options": {
            "showHundredths": _bool("Show hundredths", True),
        },
    },
    "notifications": {
        "name": "Notifications",
        "icon": "notifications",
        "width": 320,
        "corner": "middle-right",
        "options": {
            "maxItems": _int("Notifications shown", 4, 1, 12),
            "showAppName": _bool("Show application name", True),
            "showTime": _bool("Show age", True),
        },
    },
}

DEFAULT_INSTANCES: tuple[tuple[str, str, int], ...] = (
    ("clock", "top-center", 0),
    ("system", "top-right", 0),
    ("weather", "bottom-right", 0),
    ("media", "bottom-left", 0),
    ("calendar", "bottom-center", 0),
)


def default_options(widget_type: str) -> dict:
    spec = WIDGETS.get(widget_type)
    if not spec:
        return {}
    return {key: option["default"] for key, option in spec["options"].items()}


def default_instance(widget_type: str, corner: str | None = None, order: int = 0) -> dict:
    spec = WIDGETS[widget_type]
    return {
        "type": widget_type,
        "enabled": True,
        "corner": corner or spec["corner"],
        "order": order,
        "scale": 1.0,
        "options": default_options(widget_type),
    }


def default_config() -> dict:
    widgets = {f"{widget_type}-1": default_instance(widget_type, corner, order) for widget_type, corner, order in DEFAULT_INSTANCES}
    return {
        "version": 2,
        "global": {
            "cardStyle": "material",
            "opacity": 1.0,
            "edgeMargin": 28,
            "gap": 16,
            "accent": "auto",
        },
        "widgets": widgets,
    }


def migrate_v1(data: dict) -> dict:
    """Convert the old four-slot format into v2 instances."""
    global_options = dict(default_config()["global"])
    old_widgets = data.get("widgets")
    if not isinstance(old_widgets, dict) or not old_widgets:
        return default_config()

    widgets: dict[str, dict] = {}
    for old_id, old in old_widgets.items():
        if old_id not in WIDGETS or not isinstance(old, dict):
            continue
        instance_id = f"{old_id}-1"
        options = default_options(old_id)
        for key, value in old.items():
            if key in ("enabled", "corner", "scale", "order"):
                continue
            if key in options:
                options[key] = value
        widgets[instance_id] = {
            "type": old_id,
            "enabled": old.get("enabled", True) is not False,
            "corner": old.get("corner") if old.get("corner") in dict(CORNERS) else WIDGETS[old_id]["corner"],
            "order": len(widgets),
            "scale": float(old.get("scale", 1.0) or 1.0),
            "options": options,
        }

    if not widgets:
        return default_config()

    return {"version": 2, "global": global_options, "widgets": widgets}
