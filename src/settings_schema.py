"""Declarative description of every page added in the Phase 1 expansion.

Rows are plain data (no GTK) so the same spec can drive the UI, the global
search index and the unit tests.  Paths are dotted keys for ``shell.json`` or
``section:key`` names for Hyprland options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    kind: str = "bool"  # bool | int | float | enum | string | font
    default: Any = None
    subtitle: str = ""
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    digits: int = 0
    choices: tuple[tuple[Any, str], ...] = ()
    unit: str = ""
    keywords: str = ""

    def search_text(self) -> str:
        return " ".join(
            part for part in (self.label, self.subtitle, self.key, self.keywords) if part
        )


@dataclass
class Expander:
    title: str
    rows: list[Any]
    subtitle: str = ""
    keywords: str = ""


@dataclass
class Group:
    title: str
    rows: list[Any]
    description: str = ""


@dataclass
class PageSpec:
    page_id: str
    title: str
    groups: list[Group] = field(default_factory=list)
    keywords: str = ""


# ── Caelestia appearance (B1) ────────────────────────────────────────────────

APPEARANCE_SPEC = PageSpec(
    page_id="appearance",
    title="Appearance",
    keywords="shell look transparency rounding spacing padding deformation animation speed",
    groups=[
        Group(
            "Transparency",
            [
                Option(
                    "appearance.transparency.enabled",
                    "Transparency effects",
                    default=False,
                    subtitle="Blur/transparent surfaces across the shell",
                ),
                Option(
                    "appearance.transparency.base",
                    "Surface opacity",
                    kind="float",
                    default=0.85,
                    minimum=0.1,
                    maximum=1.0,
                    step=0.05,
                    digits=2,
                    subtitle="Opacity of the main surfaces (1.0 = solid)",
                ),
                Option(
                    "appearance.transparency.layers",
                    "Layer opacity",
                    kind="float",
                    default=0.4,
                    minimum=0.05,
                    maximum=1.0,
                    step=0.05,
                    digits=2,
                    subtitle="Opacity of background layers",
                ),
            ],
        ),
        Group(
            "Scaling",
            [
                Option(
                    "appearance.rounding.scale",
                    "Corner rounding",
                    kind="float",
                    default=1.0,
                    minimum=0.0,
                    maximum=2.0,
                    step=0.05,
                    digits=2,
                    subtitle="Multiplier applied to every rounding token",
                ),
                Option(
                    "appearance.spacing.scale",
                    "Spacing",
                    kind="float",
                    default=1.0,
                    minimum=0.0,
                    maximum=2.0,
                    step=0.05,
                    digits=2,
                    subtitle="Multiplier applied to every spacing token",
                ),
                Option(
                    "appearance.padding.scale",
                    "Padding",
                    kind="float",
                    default=1.0,
                    minimum=0.0,
                    maximum=2.0,
                    step=0.05,
                    digits=2,
                    subtitle="Multiplier applied to every padding token",
                ),
                Option(
                    "appearance.deformScale",
                    "Shape deformation",
                    kind="float",
                    default=1.0,
                    minimum=0.0,
                    maximum=2.0,
                    step=0.05,
                    digits=2,
                    subtitle="Blob/shape deformation strength",
                ),
                Option(
                    "appearance.anim.durations.scale",
                    "Animation speed",
                    kind="float",
                    default=1.0,
                    minimum=0.0,
                    maximum=3.0,
                    step=0.05,
                    digits=2,
                    subtitle="Duration multiplier for shell animations",
                ),
            ],
        ),
    ],
)


# ── Caelestia typography (B2) ────────────────────────────────────────────────

FONT_WEIGHTS: tuple[tuple[Any, str], ...] = (
    (100, "Thin"),
    (200, "Extra Light"),
    (300, "Light"),
    (400, "Normal"),
    (500, "Medium"),
    (600, "Semi Bold"),
    (700, "Bold"),
    (800, "Extra Bold"),
    (900, "Black"),
)

_FONT_STYLES: tuple[tuple[str, str, str, int, int, int, int], ...] = (
    # key, title, default family, large, medium, small, default weight
    ("headline", "Headline", "GoogleSansFlex", 32, 28, 24, 500),
    ("title", "Title", "GoogleSansFlex", 22, 16, 14, 500),
    ("body", "Body", "GoogleSansFlex", 16, 14, 12, 400),
    ("label", "Label", "GoogleSansFlex", 14, 12, 11, 500),
    ("mono", "Monospace", "CaskaydiaCove NF", 16, 14, 12, 400),
)


def _font_size_rows(style: str, large: int, medium: int, small: int, weight: int) -> list[Any]:
    rows: list[Any] = []
    for size_key, label, default in (
        ("large", "Large size", large),
        ("medium", "Medium size", medium),
        ("small", "Small size", small),
    ):
        rows.append(
            Option(
                f"appearance.font.{style}.{size_key}.size",
                label,
                kind="int",
                default=default,
                minimum=6,
                maximum=96,
                unit="pt",
            )
        )
        rows.append(
            Option(
                f"appearance.font.{style}.{size_key}.weight",
                f"{label} weight",
                kind="enum",
                default=weight,
                choices=FONT_WEIGHTS,
            )
        )
        rows.append(
            Option(
                f"appearance.font.{style}.{size_key}.italic",
                f"{label} italic",
                default=False,
                subtitle="Italic variant for this size",
            )
        )
    return rows


_TYPOGRAPHY_GROUPS: list[Group] = [
    Group(
        "Global",
        [
            Option(
                "appearance.font.scale",
                "Font scale",
                kind="float",
                default=1.0,
                minimum=0.5,
                maximum=2.0,
                step=0.05,
                digits=2,
                subtitle="Scales every text style at once",
            ),
            Option(
                "appearance.font.clock",
                "Clock font",
                kind="font",
                default="Rubik",
                subtitle="Used by the bar clock and desktop clock",
            ),
            Option(
                "appearance.font.workspaces",
                "Workspace font",
                kind="font",
                default="Rubik",
                subtitle="Used for workspace labels and numbers",
            ),
        ],
    )
]

for _style, _title, _family, _large, _medium, _small, _weight in _FONT_STYLES:
    _TYPOGRAPHY_GROUPS.append(
        Group(
            _title,
            [
                Expander(
                    f"{_title} text",
                    [
                        Option(
                            f"appearance.font.{_style}.family",
                            "Family",
                            kind="font",
                            default=_family,
                            subtitle="Leave empty to inherit the default",
                        ),
                        *_font_size_rows(_style, _large, _medium, _small, _weight),
                    ],
                    subtitle="Family, sizes, weights and italics",
                )
            ],
        )
    )

_TYPOGRAPHY_GROUPS.append(
    Group(
        "Icons",
        [
            Expander(
                "Icon font",
                [
                    Option(
                        "appearance.font.icon.family",
                        "Family",
                        kind="font",
                        default="Material Symbols Rounded",
                    ),
                    Option(
                        "appearance.font.icon.extraLarge.size",
                        "Extra large",
                        kind="int",
                        default=36,
                        minimum=6,
                        maximum=96,
                        unit="px",
                    ),
                    Option(
                        "appearance.font.icon.large.size",
                        "Large",
                        kind="int",
                        default=24,
                        minimum=6,
                        maximum=96,
                        unit="px",
                    ),
                    Option(
                        "appearance.font.icon.medium.size",
                        "Medium",
                        kind="int",
                        default=18,
                        minimum=6,
                        maximum=96,
                        unit="px",
                    ),
                    Option(
                        "appearance.font.icon.small.size",
                        "Small",
                        kind="int",
                        default=15,
                        minimum=6,
                        maximum=96,
                        unit="px",
                    ),
                ],
                subtitle="Material Symbols sizing",
            )
        ],
    )
)

TYPOGRAPHY_SPEC = PageSpec(
    page_id="typography",
    title="Typography",
    groups=_TYPOGRAPHY_GROUPS,
    keywords="font family size weight italic headline title body label mono icons",
)


# ── Caelestia bar (B3) ───────────────────────────────────────────────────────

BAR_ENTRY_CHOICES: tuple[tuple[str, str], ...] = (
    ("logo", "Logo"),
    ("workspaces", "Workspaces"),
    ("spacer", "Spacer"),
    ("activeWindow", "Active window"),
    ("tray", "System tray"),
    ("clock", "Clock"),
    ("statusIcons", "Status icons"),
    ("power", "Power button"),
)

BAR_ENTRY_DEFAULTS: list[dict] = [
    {"id": "logo", "enabled": True},
    {"id": "workspaces", "enabled": True},
    {"id": "spacer", "enabled": True},
    {"id": "activeWindow", "enabled": True},
    {"id": "spacer", "enabled": True},
    {"id": "tray", "enabled": True},
    {"id": "clock", "enabled": True},
    {"id": "statusIcons", "enabled": True},
    {"id": "power", "enabled": True},
]

BAR_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    ("lockStatus", "Lock status"),
    ("audio", "Audio"),
    ("microphone", "Microphone"),
    ("kbLayout", "Keyboard layout"),
    ("network", "Network"),
    ("bluetooth", "Bluetooth"),
    ("battery", "Battery"),
)

BAR_STATUS_DEFAULTS: list[dict] = [
    {"id": "lockStatus", "enabled": True},
    {"id": "audio", "enabled": False},
    {"id": "microphone", "enabled": False},
    {"id": "kbLayout", "enabled": False},
    {"id": "network", "enabled": True},
    {"id": "bluetooth", "enabled": True},
    {"id": "battery", "enabled": True},
]

WORKSPACE_DISPLAY_CHOICES: tuple[tuple[str, str], ...] = (
    ("Shapes", "Shapes"),
    ("Text", "Text"),
    ("Icons", "Icons"),
)

WORKSPACE_CAPITALISATION_CHOICES: tuple[tuple[str, str], ...] = (
    ("Preserve", "Preserve"),
    ("Upper", "UPPERCASE"),
    ("Lower", "lowercase"),
)

SPECIAL_WORKSPACE_ICON_DEFAULTS: list[dict] = [
    {"name": "special", "icon": "star"},
    {"name": "communication", "icon": "forum"},
    {"name": "music", "icon": "music_cast"},
    {"name": "todo", "icon": "checklist"},
    {"name": "sysmon", "icon": "monitor_heart"},
]

WINDOW_ICON_DEFAULTS: list[dict] = [
    {"regex": "steam(_app_(default|[0-9]+))?", "icon": "sports_esports"},
]

BAR_SPEC = PageSpec(
    page_id="bar",
    title="Bar",
    keywords="top bar panel status icons workspaces clock tray",
    groups=[
        Group(
            "Behaviour",
            [
                Option(
                    "bar.persistent",
                    "Always visible",
                    default=True,
                    subtitle="When disabled the bar hides itself",
                ),
                Option(
                    "bar.showOnHover",
                    "Show on hover",
                    default=True,
                    subtitle="Reveal the bar when the pointer reaches the edge",
                ),
                Option(
                    "bar.dragThreshold",
                    "Drag threshold",
                    kind="int",
                    default=20,
                    minimum=0,
                    maximum=200,
                    unit="px",
                ),
            ],
        ),
        Group(
            "Workspaces",
            [
                Option("bar.workspaces.shown", "Workspaces shown", kind="int", default=5, minimum=1, maximum=20),
                Option(
                    "bar.workspaces.displayType",
                    "Display style",
                    kind="enum",
                    default="Shapes",
                    choices=WORKSPACE_DISPLAY_CHOICES,
                ),
                Option(
                    "bar.workspaces.specialDisplayType",
                    "Special display style",
                    kind="enum",
                    default="Icons",
                    choices=WORKSPACE_DISPLAY_CHOICES,
                ),
                Option(
                    "bar.workspaces.capitalisation",
                    "Capitalisation",
                    kind="enum",
                    default="Preserve",
                    choices=WORKSPACE_CAPITALISATION_CHOICES,
                ),
                Option("bar.workspaces.activeIndicator", "Active indicator", default=True),
                Option("bar.workspaces.activeTrail", "Active trail", default=True),
                Option("bar.workspaces.occupiedBg", "Background for occupied", default=False),
                Option("bar.workspaces.showUnoccupied", "Show unoccupied", default=True),
                Option("bar.workspaces.perMonitor", "Per-monitor workspaces", default=True),
                Option("bar.workspaces.showWindows", "Show window icons", default=True),
                Option(
                    "bar.workspaces.showWindowsOnSpecialWorkspaces",
                    "Window icons on special workspaces",
                    default=True,
                ),
                Option(
                    "bar.workspaces.maxWindowIcons",
                    "Max window icons",
                    kind="int",
                    default=5,
                    minimum=0,
                    maximum=20,
                ),
                Option("bar.workspaces.label", "Workspace label", kind="string", default="\uf444  "),
                Option("bar.workspaces.occupiedLabel", "Occupied label", kind="string", default="󰮯"),
                Option("bar.workspaces.activeLabel", "Active label", kind="string", default="󰮯"),
            ],
        ),
        Group(
            "Clock",
            [
                Option("bar.clock.background", "Background", default=False),
                Option("bar.clock.showDate", "Show date", default=False),
                Option("bar.clock.showIcon", "Show icon", default=True),
                Option("bar.clock.showSeconds", "Show seconds", default=False),
            ],
        ),
        Group(
            "Tray",
            [
                Option("bar.tray.background", "Background", default=False),
                Option("bar.tray.recolour", "Recolour icons", default=False),
                Option("bar.tray.compact", "Compact", default=False),
            ],
        ),
        Group(
            "Active window",
            [
                Option("bar.activeWindow.compact", "Compact", default=False),
                Option("bar.activeWindow.inverted", "Inverted", default=False),
                Option("bar.activeWindow.showOnHover", "Show on hover", default=True),
            ],
        ),
        Group(
            "Popouts",
            [
                Option("bar.popouts.activeWindow", "Active window popout", default=True),
                Option("bar.popouts.tray", "Tray popout", default=True),
                Option("bar.popouts.statusIcons", "Status icons popout", default=True),
            ],
        ),
        Group(
            "Scroll actions",
            [
                Option("bar.scrollActions.workspaces", "Scroll workspaces", default=True),
                Option("bar.scrollActions.volume", "Scroll volume", default=True),
                Option("bar.scrollActions.brightness", "Scroll brightness", default=True),
            ],
        ),
    ],
)


# ── Hyprland: general & layouts (C1) ─────────────────────────────────────────

HYPR_GENERAL_SPEC = PageSpec(
    page_id="hypr-general",
    title="Hyprland: General",
    keywords="hyprland layout gaps borders tearing snap dwindle master scrolling",
    groups=[
        Group(
            "Layout",
            [
                Option(
                    "general:layout",
                    "Window layout",
                    kind="enum",
                    default="dwindle",
                    choices=(("dwindle", "Dwindle"), ("master", "Master"), ("scrolling", "Scrolling (niri-like)")),
                ),
                Option("general:allow_tearing", "Allow tearing", subtitle="Needed by the immediate window rule"),
                Option("general:resize_on_border", "Resize on border", subtitle="Drag window edges to resize"),
                Option("general:snap:enabled", "Window snapping", subtitle="Snap windows to edges of other windows"),
            ],
        ),
        Group(
            "Gaps and borders",
            [
                Option("general:gaps_in", "Inner gaps", kind="int", default=5, minimum=0, maximum=100, unit="px"),
                Option("general:gaps_out", "Outer gaps", kind="int", default=10, minimum=0, maximum=200, unit="px"),
                Option(
                    "general:gaps_workspaces",
                    "Workspace gaps",
                    kind="int",
                    default=0,
                    minimum=0,
                    maximum=200,
                    unit="px",
                ),
                Option("general:border_size", "Border size", kind="int", default=1, minimum=0, maximum=20, unit="px"),
            ],
        ),
        Expander(
            "Scrolling layout",
            [
                Option(
                    "scrolling:direction",
                    "Direction",
                    kind="enum",
                    default="right",
                    choices=(("left", "Left"), ("right", "Right"), ("up", "Up"), ("down", "Down")),
                ),
                Option(
                    "scrolling:column_width",
                    "Default column width",
                    kind="float",
                    default=0.5,
                    minimum=0.1,
                    maximum=2.0,
                    step=0.05,
                    digits=2,
                    subtitle="Fraction of the screen width",
                ),
                Option("scrolling:follow_focus", "Follow focus", default=True),
                Option(
                    "scrolling:follow_min_visible",
                    "Minimum visible when following",
                    kind="float",
                    default=0.0,
                    minimum=0.0,
                    maximum=1.0,
                    step=0.05,
                    digits=2,
                ),
                Option("scrolling:wrap_focus", "Wrap focus", default=True),
                Option("scrolling:wrap_swapcol", "Wrap column swapping", default=True),
                Option("scrolling:fullscreen_on_one_column", "Fullscreen single column", default=False),
                Option(
                    "scrolling:focus_fit_method",
                    "Focus fit method",
                    kind="enum",
                    default=1,
                    choices=((0, "Center"), (1, "Fit to view")),
                ),
                Option(
                    "scrolling:explicit_column_widths",
                    "Preset column widths",
                    kind="string",
                    default="0.35, 0.5, 0.65, 1.0",
                    subtitle="Comma-separated widths cycled by the resize binds",
                ),
            ],
            subtitle="Only used when the layout is set to scrolling",
        ),
        Expander(
            "Dwindle layout",
            [
                Option("dwindle:preserve_split", "Preserve split", default=True),
                Option("dwindle:smart_split", "Smart split", default=False),
                Option("dwindle:smart_resizing", "Smart resizing", default=True),
                Option(
                    "dwindle:force_split",
                    "Force split direction",
                    kind="enum",
                    default=0,
                    choices=((0, "Follow mouse"), (1, "Opposite direction"), (2, "Direction")),
                ),
                Option("dwindle:default_split_ratio", "Default split ratio", kind="float", default=1.0, minimum=0.1, maximum=2.0, step=0.05, digits=2),
                Option("dwindle:special_scale_factor", "Special workspace scale", kind="float", default=1.0, minimum=0.1, maximum=1.0, step=0.05, digits=2),
                Option("dwindle:use_active_for_splits", "Use active window for splits", default=True),
                Option("dwindle:permanent_direction_override", "Permanent direction override", default=False),
            ],
            subtitle="Only used when the layout is set to dwindle",
        ),
        Expander(
            "Master layout",
            [
                Option("master:mfact", "Master factor", kind="float", default=0.55, minimum=0.1, maximum=0.9, step=0.05, digits=2),
                Option(
                    "master:new_status",
                    "New window status",
                    kind="enum",
                    default="slave",
                    choices=(("master", "Master"), ("slave", "Slave"), ("inherit", "Inherit")),
                ),
                Option("master:new_on_top", "New window on top", default=False),
                Option(
                    "master:new_on_active",
                    "New window position",
                    kind="enum",
                    default="none",
                    choices=(("none", "Default"), ("before", "Before active"), ("after", "After active")),
                ),
                Option(
                    "master:orientation",
                    "Orientation",
                    kind="enum",
                    default="left",
                    choices=(("left", "Left"), ("right", "Right"), ("top", "Top"), ("bottom", "Bottom"), ("center", "Center")),
                ),
                Option("master:slave_count_for_center_master", "Slaves needed to center master", kind="int", default=2, minimum=1, maximum=10),
                Option("master:allow_small_split", "Allow small split", default=False),
                Option("master:special_scale_factor", "Special workspace scale", kind="float", default=1.0, minimum=0.1, maximum=1.0, step=0.05, digits=2),
                Option("master:smart_resizing", "Smart resizing", default=True),
                Option("master:drop_at_cursor", "Drop at cursor", default=True),
            ],
            subtitle="Only used when the layout is set to master",
        ),
    ],
)


# ── Hyprland: decoration (C2) ────────────────────────────────────────────────

HYPR_DECORATION_SPEC = PageSpec(
    page_id="hypr-decor",
    title="Hyprland: Decoration",
    keywords="hyprland decoration rounding opacity blur shadow dim borders",
    groups=[
        Group(
            "Windows",
            [
                Option("decoration:rounding", "Corner rounding", kind="int", default=0, minimum=0, maximum=50, unit="px"),
                Option("decoration:rounding_power", "Rounding power", kind="float", default=2.0, minimum=1.0, maximum=10.0, step=0.5, digits=1),
                Option("decoration:active_opacity", "Active opacity", kind="float", default=1.0, minimum=0.1, maximum=1.0, step=0.05, digits=2),
                Option("decoration:inactive_opacity", "Inactive opacity", kind="float", default=1.0, minimum=0.1, maximum=1.0, step=0.05, digits=2),
                Option("decoration:dim_inactive", "Dim inactive windows", default=False),
                Option("decoration:dim_strength", "Dim strength", kind="float", default=0.5, minimum=0.0, maximum=1.0, step=0.05, digits=2),
            ],
        ),
        Expander(
            "Blur",
            [
                Option("decoration:blur:enabled", "Enable blur", default=True),
                Option("decoration:blur:size", "Blur size", kind="int", default=8, minimum=0, maximum=30),
                Option("decoration:blur:passes", "Blur passes", kind="int", default=2, minimum=0, maximum=10),
                Option("decoration:blur:xray", "X-ray blur", default=False),
                Option("decoration:blur:special", "Blur special workspaces", default=False),
                Option("decoration:blur:popups", "Blur popups", default=True),
                Option("decoration:blur:input_methods", "Blur input methods", default=True),
                Option("decoration:blur:ignore_opacity", "Blur transparent windows", default=True),
                Option("decoration:blur:new_optimizations", "New optimizations", default=True),
            ],
            subtitle="Background blur of windows and layers",
        ),
        Expander(
            "Shadows",
            [
                Option("decoration:shadow:enabled", "Enable shadows", default=True),
                Option("decoration:shadow:range", "Shadow range", kind="int", default=15, minimum=0, maximum=100),
                Option("decoration:shadow:render_power", "Render power", kind="int", default=4, minimum=1, maximum=10),
                Option("decoration:shadow:sharp", "Sharp shadows", default=False),
            ],
            subtitle="Window drop shadows",
        ),
    ],
)


# ── Hyprland: input (C4) ─────────────────────────────────────────────────────

HYPR_INPUT_SPEC = PageSpec(
    page_id="hypr-input",
    title="Hyprland: Input",
    keywords="hyprland input keyboard layout variant options touchpad mouse sensitivity repeat numlock",
    groups=[
        Group(
            "Keyboard",
            [
                Option(
                    "input:kb_variant",
                    "Variants",
                    kind="string",
                    default="",
                    subtitle="Comma-separated, e.g. ,intl",
                ),
                Option(
                    "input:kb_options",
                    "Options",
                    kind="string",
                    default="",
                    subtitle="Comma-separated XKB options, e.g. grp:alt_shift_toggle",
                ),
                Option("input:repeat_rate", "Repeat rate", kind="int", default=25, minimum=1, maximum=100, unit="Hz"),
                Option("input:repeat_delay", "Repeat delay", kind="int", default=250, minimum=100, maximum=1000, unit="ms"),
            ],
            description="Keyboard layouts and NumLock are managed on the General page; this page adds the advanced XKB options and repeat settings.",
        ),
        Group(
            "Mouse",
            [
                Option("input:sensitivity", "Sensitivity", kind="float", default=0.0, minimum=-1.0, maximum=1.0, step=0.05, digits=2),
                Option(
                    "input:accel_profile",
                    "Acceleration profile",
                    kind="enum",
                    default="",
                    choices=(("", "Default"), ("adaptive", "Adaptive"), ("flat", "Flat (no acceleration)"), ("custom", "Custom")),
                ),
                Option(
                    "input:scroll_method",
                    "Scroll method",
                    kind="enum",
                    default="",
                    choices=(("", "Default"), ("2fg", "Two fingers"), ("edge", "Edge"), ("on_button_down", "On button down"), ("no_scroll", "No scroll")),
                ),
                Option("input:scroll_button", "Scroll button", kind="int", default=0, minimum=0, maximum=20),
                Option("input:emulate_discrete_scroll", "Emulate discrete scroll", kind="int", default=1, minimum=0, maximum=2),
                Option("input:mouse_refocus", "Refocus on mouse move", default=True),
            ],
        ),
        Group(
            "Touchpad",
            [
                Option("input:touchpad:natural_scroll", "Natural scroll", default=True),
                Option("input:touchpad:disable_while_typing", "Disable while typing", default=True),
                Option("input:touchpad:tap-to-click", "Tap to click", default=True),
                Option("input:touchpad:tap-and-drag", "Tap and drag", default=True),
                Option(
                    "input:touchpad:drag_lock",
                    "Drag lock",
                    kind="enum",
                    default=0,
                    choices=((0, "Disabled"), (1, "Enabled"), (2, "Timeout")),
                ),
                Option(
                    "input:touchpad:clickfinger_behavior",
                    "Clickfinger behaviour",
                    default=False,
                    subtitle="2-finger right click, 3-finger middle click",
                ),
                Option("input:touchpad:middle_button_emulation", "Middle button emulation", default=False),
                Option(
                    "input:touchpad:tap_button_map",
                    "Tap button map",
                    kind="enum",
                    default="",
                    choices=(("", "Default"), ("lmr", "Left / Middle / Right"), ("lrm", "Left / Right / Middle")),
                ),
                Option(
                    "input:touchpad:scroll_factor",
                    "Scroll factor",
                    kind="float",
                    default=1.0,
                    minimum=0.1,
                    maximum=3.0,
                    step=0.05,
                    digits=2,
                ),
            ],
        ),
        Group(
            "Focus and binds",
            [
                Option(
                    "input:follow_mouse",
                    "Follow mouse",
                    kind="enum",
                    default=1,
                    choices=((0, "Disabled"), (1, "Full"), (2, "Loose"), (3, "Full (special workspaces)")),
                ),
                Option(
                    "input:follow_mouse_shrink",
                    "Mouse focus dead zone",
                    kind="int",
                    default=0,
                    minimum=0,
                    maximum=300,
                    unit="px",
                    subtitle="Edge of inactive windows that will not grab focus (works with Follow mouse = Full)",
                ),
                Option("input:special_fallthrough", "Special workspace fallthrough", default=False),
                Option("input:focus_on_close", "Focus on close", kind="int", default=1, minimum=0, maximum=2),
                Option("binds:scroll_event_delay", "Scroll event delay", kind="int", default=0, minimum=0, maximum=1000, unit="ms"),
            ],
        ),
    ],
)


# ── Caelestia launcher (B4) ──────────────────────────────────────────────────

LAUNCHER_SPEC = PageSpec(
    page_id="launcher",
    title="Launcher",
    keywords="launcher spotlight search applications actions wallpaper scheme",
    groups=[
        Group(
            "Behaviour",
            [
                Option("launcher.enabled", "Enable launcher", default=True),
                Option("launcher.showOnHover", "Show on hover", default=False),
                Option("launcher.maxShown", "Maximum results", kind="int", default=7, minimum=1, maximum=50),
                Option("launcher.maxWallpapers", "Maximum wallpapers", kind="int", default=9, minimum=1, maximum=50),
                Option("launcher.dragThreshold", "Drag threshold", kind="int", default=50, minimum=0, maximum=200, unit="px"),
            ],
        ),
        Group(
            "Prefixes",
            [
                Option("launcher.specialPrefix", "Special search prefix", kind="string", default="@", subtitle="Prefix for special searches"),
                Option("launcher.actionPrefix", "Action prefix", kind="string", default=">", subtitle="Prefix for launcher actions"),
                Option("launcher.enableDangerousActions", "Enable dangerous actions", default=False, subtitle="Shutdown, reboot and logout actions"),
            ],
        ),
        Group(
            "Fuzzy search",
            [
                Option("launcher.useFuzzy.apps", "Applications", default=False),
                Option("launcher.useFuzzy.actions", "Actions", default=False),
                Option("launcher.useFuzzy.schemes", "Colour schemes", default=False),
                Option("launcher.useFuzzy.variants", "Scheme variants", default=False),
                Option("launcher.useFuzzy.wallpapers", "Wallpapers", default=False),
            ],
        ),
        Group(
            "Keyboard",
            [
                Option("launcher.vimKeybinds", "Vim keybinds", default=False),
            ],
        ),
    ],
)


# ── Caelestia dashboard (B5) ─────────────────────────────────────────────────

DASHBOARD_SPEC = PageSpec(
    page_id="dashboard",
    title="Dashboard",
    keywords="dashboard media performance weather clock battery cpu gpu memory",
    groups=[
        Group(
            "Dashboard",
            [
                Option("dashboard.enabled", "Enable dashboard", default=True),
                Option("dashboard.showOnHover", "Show on hover", default=True),
                Option("dashboard.showDashboard", "Show dashboard panel", default=True),
                Option("dashboard.showMedia", "Show media player", default=True),
                Option("dashboard.showPerformance", "Show performance", default=True),
                Option("dashboard.showWeather", "Show weather", default=True),
                Option("dashboard.showClockSeconds", "Show seconds in clock", default=False),
                Option("dashboard.dragThreshold", "Drag threshold", kind="int", default=50, minimum=0, maximum=200, unit="px"),
            ],
        ),
        Group(
            "Performance cards",
            [
                Option("dashboard.performance.showBattery", "Battery", default=True),
                Option("dashboard.performance.showGpu", "GPU", default=True),
                Option("dashboard.performance.showCpu", "CPU", default=True),
                Option("dashboard.performance.showMemory", "Memory", default=True),
                Option("dashboard.performance.showStorage", "Storage", default=True),
                Option("dashboard.performance.showNetwork", "Network", default=True),
            ],
        ),
        Group(
            "Refresh intervals",
            [
                Option("dashboard.mediaUpdateInterval", "Media update interval", kind="int", default=500, minimum=100, maximum=10000, unit="ms"),
                Option("dashboard.resourceUpdateInterval", "Resource update interval", kind="int", default=1000, minimum=100, maximum=10000, unit="ms"),
            ],
        ),
    ],
)


# ── Caelestia sidebar & utilities (B6) ───────────────────────────────────────

QUICK_TOGGLE_CHOICES: tuple[tuple[str, str], ...] = (
    ("wifi", "Wi-Fi"),
    ("bluetooth", "Bluetooth"),
    ("mic", "Microphone"),
    ("settings", "Settings"),
    ("gameMode", "Game mode"),
    ("dnd", "Do not disturb"),
    ("vpn", "VPN"),
)

QUICK_TOGGLE_DEFAULTS: list[dict] = [
    {"id": "wifi", "enabled": True},
    {"id": "bluetooth", "enabled": True},
    {"id": "mic", "enabled": True},
    {"id": "settings", "enabled": True},
    {"id": "gameMode", "enabled": True},
    {"id": "dnd", "enabled": True},
    {"id": "vpn", "enabled": False},
]

TOAST_CHOICES: tuple[tuple[str, str], ...] = (
    ("off", "Off"),
    ("important", "Important only"),
    ("all", "All"),
)

SIDEBAR_UTILITIES_SPEC = PageSpec(
    page_id="sidebar",
    title="Sidebar & Utilities",
    keywords="sidebar utilities quick toggles toasts vpn cards keep awake recorder",
    groups=[
        Group(
            "Sidebar",
            [
                Option("sidebar.enabled", "Enable sidebar", default=True),
                Option("sidebar.showOnHover", "Show on hover", default=False),
                Option("sidebar.minHoverThreshold", "Minimum hover threshold", kind="int", default=200, minimum=0, maximum=2000, unit="ms"),
                Option("sidebar.dragThreshold", "Drag threshold", kind="int", default=80, minimum=0, maximum=300, unit="px"),
            ],
        ),
        Group(
            "Utilities",
            [
                Option("utilities.enabled", "Enable utilities", default=True),
                Option("utilities.maxToasts", "Maximum toasts", kind="int", default=4, minimum=1, maximum=20),
                Option("utilities.cards.keepAwake", "Keep awake card", default=True),
                Option("utilities.cards.recorder", "Recorder card", default=True),
                Option("utilities.cards.quickToggles", "Quick toggles card", default=True),
            ],
        ),
        Group(
            "Toast visibility",
            [
                Option("utilities.toasts.fullscreen", "Fullscreen policy", kind="enum", default="off", choices=TOAST_CHOICES),
                Option("utilities.toasts.configLoaded", "Configuration loaded", default=True),
                Option("utilities.toasts.chargingChanged", "Charging changed", default=True),
                Option("utilities.toasts.gameModeChanged", "Game mode changed", default=True),
                Option("utilities.toasts.dndChanged", "Do not disturb changed", default=True),
                Option("utilities.toasts.audioOutputChanged", "Audio output changed", default=True),
                Option("utilities.toasts.audioInputChanged", "Audio input changed", default=True),
                Option("utilities.toasts.capsLockChanged", "Caps Lock changed", default=True),
                Option("utilities.toasts.numLockChanged", "Num Lock changed", default=True),
                Option("utilities.toasts.kbLayoutChanged", "Keyboard layout changed", default=True),
                Option("utilities.toasts.kbLimit", "Keyboard limit", default=True),
                Option("utilities.toasts.vpnChanged", "VPN changed", default=True),
                Option("utilities.toasts.nowPlaying", "Now playing", default=False),
            ],
        ),
        Group(
            "VPN",
            [
                Option("utilities.vpn.enabled", "Enable VPN integration", default=False),
                Option("utilities.vpn.selectedProvider", "Selected provider", kind="string", default=""),
            ],
        ),
    ],
)


# ── Caelestia notifications & OSD (B7) ───────────────────────────────────────

NOTIFS_FULLSCREEN_CHOICES: tuple[tuple[str, str], ...] = (
    ("On", "Show over fullscreen"),
    ("Off", "Hide over fullscreen"),
)

NOTIFICATIONS_SPEC = PageSpec(
    page_id="notifications",
    title="Notifications",
    keywords="notifications osd popup timeout fullscreen microphone brightness",
    groups=[
        Group(
            "Notifications",
            [
                Option("notifs.expire", "Expire automatically", default=True),
                Option("notifs.fullscreen", "Fullscreen behaviour", kind="enum", default="On", choices=NOTIFS_FULLSCREEN_CHOICES),
                Option("notifs.defaultExpireTimeout", "Default timeout", kind="int", default=5000, minimum=0, maximum=60000, unit="ms"),
                Option("notifs.fullscreenExpireTimeout", "Fullscreen timeout", kind="int", default=2000, minimum=0, maximum=60000, unit="ms"),
                Option("notifs.clearThreshold", "Clear threshold", kind="float", default=0.3, minimum=0.0, maximum=1.0, step=0.05, digits=2, subtitle="Swipe distance needed to dismiss"),
                Option("notifs.expandThreshold", "Expand threshold", kind="int", default=20, minimum=0, maximum=200, subtitle="Notifications needed to group"),
                Option("notifs.actionOnClick", "Run action on click", default=False),
                Option("notifs.groupPreviewNum", "Group preview count", kind="int", default=3, minimum=0, maximum=20),
                Option("notifs.openExpanded", "Open expanded", default=False),
            ],
        ),
        Group(
            "On-screen display",
            [
                Option("osd.enabled", "Enable OSD", default=True),
                Option("osd.hideDelay", "Hide delay", kind="int", default=2000, minimum=200, maximum=10000, unit="ms"),
                Option("osd.enableBrightness", "Show brightness changes", default=True),
                Option("osd.enableMicrophone", "Show microphone changes", default=False),
            ],
        ),
    ],
)


# ── Caelestia lock screen (B8) ───────────────────────────────────────────────

LOCK_SPEC = PageSpec(
    page_id="lock",
    title="Lock Screen",
    keywords="lock screen wallpaper fingerprint howdy face unlock session notifications",
    groups=[
        Group(
            "Appearance",
            [
                Option("lock.enabled", "Enable lock screen", default=True),
                Option("lock.useWallpaper", "Use wallpaper as background", default=False),
                Option("lock.recolourLogo", "Recolour logo", default=True),
                Option("lock.hideNotifs", "Hide notifications", default=False),
            ],
        ),
        Group(
            "Authentication",
            [
                Option("lock.enableFprint", "Fingerprint unlock", default=True),
                Option("lock.maxFprintTries", "Maximum fingerprint tries", kind="int", default=3, minimum=1, maximum=10),
                Option("lock.enableHowdy", "Howdy face unlock", default=True),
                Option("lock.maxHowdyTries", "Maximum Howdy tries", kind="int", default=3, minimum=1, maximum=10),
                Option("lock.triggerHowdyOnWake", "Trigger Howdy on wake", default=True),
            ],
        ),
        Group(
            "Session",
            [
                Option("lock.enableSessionControls", "Show session controls", default=False),
            ],
        ),
    ],
)


# ── Caelestia idle, power & battery (B9) ─────────────────────────────────────

IDLE_TIMEOUT_DEFAULTS: list[dict] = [
    {"enabled": True, "timeout": 180, "idleAction": "lock"},
    {"enabled": True, "timeout": 300, "idleAction": "dpms off", "returnAction": "dpms on"},
    {"enabled": True, "timeout": 600, "idleAction": ["suspendThenHibernate"]},
]

BATTERY_WARN_DEFAULTS: list[dict] = [
    {"level": 20, "title": "Low battery", "message": "You might want to plug in a charger", "icon": "battery_android_frame_2", "critical": False},
    {"level": 10, "title": "Did you see the previous message?", "message": "You should probably plug in a charger <b>now</b>", "icon": "battery_android_frame_1", "critical": False},
    {"level": 5, "title": "Critical battery level", "message": "PLUG THE CHARGER RIGHT NOW!!", "icon": "battery_android_alert", "critical": True},
]

POWER_SPEC = PageSpec(
    page_id="power",
    title="Power & Idle",
    keywords="idle timeout suspend hibernate lock battery charge power",
    groups=[
        Group(
            "Idle",
            [
                Option("general.idle.lockBeforeSleep", "Lock before sleep", default=True),
                Option("general.idle.inhibitWhenAudio", "Inhibit idle while audio plays", default=True),
                Option("general.idle.inhibitWhenCharging", "Inhibit idle while charging", default=False),
            ],
        ),
        Group(
            "Battery",
            [
                Option("general.battery.criticalLevel", "Critical level", kind="int", default=3, minimum=0, maximum=20, unit="%"),
            ],
        ),
    ],
)


# ── Caelestia services (B10) ─────────────────────────────────────────────────

TEMPERATURE_UNIT_CHOICES: tuple[tuple[str, str], ...] = (
    ("Auto", "Automatic"),
    ("Celsius", "Celsius"),
    ("Fahrenheit", "Fahrenheit"),
    ("Kelvin", "Kelvin"),
)

DATA_UNIT_CHOICES: tuple[tuple[str, str], ...] = (
    ("Binary", "Binary (KiB/MiB/GiB)"),
    ("Decimal", "Decimal (KB/MB/GB)"),
)

CLOCK_FORMAT_CHOICES: tuple[tuple[str, str], ...] = (
    ("Auto", "Automatic"),
    ("TwelveHour", "12-hour"),
    ("TwentyFourHour", "24-hour"),
)

GPU_TYPE_CHOICES: tuple[tuple[str, str], ...] = (
    ("Auto", "Automatic"),
    ("Nvidia", "NVIDIA"),
    ("Generic", "Generic"),
    ("None", "None"),
)

LYRICS_BACKEND_CHOICES: tuple[tuple[str, str], ...] = (
    ("Auto", "Automatic"),
    ("Local", "Local files"),
    ("LRCLIB", "LRCLIB"),
    ("NetEase", "NetEase"),
)

SERVICES_SPEC = PageSpec(
    page_id="services",
    title="Services",
    keywords="weather units clock format gpu visualiser volume audio brightness lyrics player",
    groups=[
        Group(
            "Weather",
            [
                Option("services.weatherLocation", "Location", kind="string", default="", subtitle="Leave empty to detect automatically"),
                Option("services.weatherUnits", "Temperature units", kind="enum", default="Auto", choices=TEMPERATURE_UNIT_CHOICES),
            ],
        ),
        Group(
            "Units and formats",
            [
                Option("services.sensorUnits", "Sensor units", kind="enum", default="Celsius", choices=TEMPERATURE_UNIT_CHOICES),
                Option("services.dataUnits", "Data units", kind="enum", default="Binary", choices=DATA_UNIT_CHOICES),
                Option("services.clockFormat", "Clock format", kind="enum", default="Auto", choices=CLOCK_FORMAT_CHOICES),
                Option("services.gpuType", "GPU type", kind="enum", default="Auto", choices=GPU_TYPE_CHOICES),
            ],
        ),
        Group(
            "Media",
            [
                Option("services.defaultPlayer", "Default player", kind="string", default="Spotify"),
                Option("services.lyricsBackend", "Lyrics backend", kind="enum", default="Auto", choices=LYRICS_BACKEND_CHOICES),
                Option("services.visualiserBars", "Visualiser bars", kind="int", default=60, minimum=8, maximum=256),
            ],
        ),
        Group(
            "Audio and brightness",
            [
                Option("services.audioIncrement", "Volume step", kind="int", default=10, minimum=1, maximum=50, step=1, unit="%", subtitle="Also applies to the hardware volume keys"),
                Option("services.brightnessIncrement", "Brightness step", kind="int", default=10, minimum=1, maximum=50, step=1, unit="%", subtitle="Also applies to the hardware brightness keys"),
                Option("services.maxVolume", "Maximum volume", kind="int", default=100, minimum=10, maximum=200, step=5, unit="%", subtitle="Also limits the hardware volume keys"),
            ],
        ),
        Group(
            "Theme",
            [
                Option("services.smartScheme", "Smart colour scheme", default=True),
            ],
        ),
    ],
)


# ── Hyprland animations & gestures (C3 / C5) ─────────────────────────────────

HYPR_ANIMATIONS_SPEC = PageSpec(
    page_id="hypr-anim",
    title="Hyprland: Animations",
    keywords="hyprland animations curves bezier speed windows workspaces layers fade",
    groups=[
        Group(
            "Engine",
            [
                Option("animations:enabled", "Enable animations", default=True),
            ],
        )
    ],
)

HYPR_GESTURES_SPEC = PageSpec(
    page_id="hypr-gestures",
    title="Hyprland: Gestures",
    keywords="hyprland gestures swipe touchpad workspace fingers scroll direction",
    groups=[
        Group(
            "Workspace swipe",
            [
                Option("gestures:workspace_swipe_distance", "Swipe distance", kind="int", default=700, minimum=100, maximum=3000, unit="px"),
                Option("gestures:workspace_swipe_cancel_ratio", "Cancel ratio", kind="float", default=0.15, minimum=0.0, maximum=1.0, step=0.01, digits=2),
                Option("gestures:workspace_swipe_min_speed_to_force", "Minimum speed to force", kind="int", default=5, minimum=0, maximum=100),
                Option("gestures:workspace_swipe_direction_lock", "Direction lock", default=True),
                Option("gestures:workspace_swipe_direction_lock_threshold", "Direction lock threshold", kind="int", default=10, minimum=0, maximum=200, unit="px"),
                Option("gestures:workspace_swipe_create_new", "Create new workspace", default=True),
                Option("gestures:workspace_swipe_forever", "Swipe forever", default=False),
                Option("gestures:workspace_swipe_touch", "Touch gestures", default=False),
                Option("gestures:workspace_swipe_invert", "Invert direction", default=False),
                Option("gestures:workspace_swipe_use_r", "Use relative workspace names", default=False),
                Option("gestures:close_max_timeout", "Close gesture timeout", kind="int", default=1000, minimum=0, maximum=5000, unit="ms"),
            ],
        )
    ],
)


# ── Per-monitor shell overrides (A8) ─────────────────────────────────────────

CLOCK_POSITION_CHOICES: tuple[tuple[str, str], ...] = (
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

MONITOR_OVERRIDE_SPEC = PageSpec(
    page_id="monitor-overrides",
    title="Per-monitor overrides",
    keywords="monitor override per screen bar clock wallpaper appearance",
    groups=[
        Group(
            "Bar",
            [
                Option("bar.persistent", "Always visible", default=True),
                Option("bar.showOnHover", "Show on hover", default=True),
                Option("bar.workspaces.shown", "Workspaces shown", kind="int", default=5, minimum=1, maximum=20),
                Option("bar.workspaces.perMonitor", "Per-monitor workspaces", default=True),
                Option("bar.clock.showDate", "Clock: show date", default=False),
                Option("bar.clock.showSeconds", "Clock: show seconds", default=False),
                Option("bar.activeWindow.compact", "Compact active window", default=False),
            ],
        ),
        Group(
            "Desktop clock",
            [
                Option("background.desktopClock.enabled", "Show clock", default=False),
                Option("background.desktopClock.position", "Position", kind="enum", default="bottom-right", choices=CLOCK_POSITION_CHOICES),
                Option("background.desktopClock.scale", "Scale", kind="float", default=1.0, minimum=0.5, maximum=3.0, step=0.05, digits=2),
                Option("background.desktopClock.invertColors", "Invert colours", default=False),
            ],
        ),
        Group(
            "Wallpaper and look",
            [
                Option("background.wallpaperEnabled", "Show wallpaper", default=True),
                Option("appearance.rounding.scale", "Corner rounding scale", kind="float", default=1.0, minimum=0.0, maximum=2.0, step=0.05, digits=2),
                Option("appearance.spacing.scale", "Spacing scale", kind="float", default=1.0, minimum=0.0, maximum=2.0, step=0.05, digits=2),
            ],
        ),
    ],
)


# ── SDDM login theme (D9) ────────────────────────────────────────────────────

LOGIN_THEME_SPEC = PageSpec(
    page_id="login-theme",
    title="Login Theme",
    keywords="sddm login locklike theme welcome avatar clock",
    groups=[
        Group(
            "Login screen",
            [
                Option("enableWelcomeMessage", "Show welcome message", default=True),
                Option("sessionPicker", "Show session picker", default=True),
                Option("ap", "Use 12-hour clock", default=False),
                Option(
                    "AvatarShape",
                    "Avatar shape",
                    kind="enum",
                    default="hexagon",
                    choices=(("hexagon", "Hexagon"), ("circle", "Circle")),
                ),
                Option("backgroundVideoEnabled", "Video background", default=True, subtitle="Requires qt6-multimedia"),
            ],
        ),
        Group(
            "Welcome panel",
            [
                Option("welcomeBgBlur", "Blur background", default=True),
                Option("welcomeBgBlurAmount", "Background blur amount", kind="float", default=0.7, minimum=0.0, maximum=1.0, step=0.05, digits=2),
                Option("welcomeColorOpacity", "Background opacity", kind="float", default=0.7, minimum=0.0, maximum=1.0, step=0.05, digits=2),
            ],
        ),
        Group(
            "Main card",
            [
                Option("mainCardBgBlur", "Blur card background", default=True),
                Option("mainCardBlurAmount", "Card blur amount", kind="float", default=0.9, minimum=0.0, maximum=1.0, step=0.05, digits=2),
                Option("mainCardColorOpacity", "Card opacity", kind="float", default=0.9, minimum=0.0, maximum=1.0, step=0.05, digits=2),
                Option("mainCardComponentsOpacity", "Component opacity", kind="float", default=0.9, minimum=0.0, maximum=1.0, step=0.05, digits=2),
            ],
        ),
    ],
)
