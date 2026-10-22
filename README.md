# Caelestia Settings (personal fork)

> A native GTK4/Libadwaita control center for [Caelestia](https://github.com/caelestia-dots/caelestia) Hyprland setups.
>
> This is a personal fork of [Jojo252511/caelestia-settings](https://github.com/Jojo252511/caelestia-settings), maintained by [OscarJDA](https://github.com/OscarJDA). It adds a schema-driven settings engine, 41 configuration pages, a Hyprland override layer, full Spanish (Mexico) localization and several hotfixes.

![Version](https://img.shields.io/badge/version-1.7.0-blue)
![Platform](https://img.shields.io/badge/platform-Arch%20Linux-1793d1)
![License](https://img.shields.io/badge/license-MIT-green)
![Language](https://img.shields.io/badge/i18n-EN%20%2F%20DE%20%2F%20ES-orange)

---

## Features

### Home
- System at a Glance overview: current wallpaper (thumbnail preview), monitors summary, active Wi-Fi connection, keyboard layout, CPU/GPU temperatures with fan speeds
- Quick Actions for one-click navigation to Wallpaper, Monitor, WLAN, Keybinds, and Updates pages

### Desktop Widgets
- Enable and position the native desktop clock and audio visualiser
- System monitor, weather, media and calendar widgets, stored in `~/.config/caelestia-settings/desktop_widgets.json`
- Fixed corner placement with per-widget scale and visibility controls

### Wallpaper
- Image and video tabs — browse `~/Pictures/Wallpapers/` and `~/Videos/Wallpaper/`
- Thumbnails generated via ffmpeg for videos, cached for fast reloads
- Wallpaper folder dynamically read from `~/.config/caelestia/shell.json`
- One-click random wallpaper via `caelestia wallpaper -r`
- Light / Dark mode toggle (`caelestia scheme set -m light/dark`)
- Desktop clock settings — toggle, position, scale and invert colors (written to `shell.json`)

### Monitor
- Interactive drag-and-drop canvas — arrange monitors visually like Windows/GNOME
- Per-monitor settings: resolution, refresh rate, rotation, bit depth (8/10-bit HDR), scale
- Set primary monitor (`xrandr --primary` via `execs.conf`)
- Toggle taskbar visibility per monitor (`shell.json: bar.persistent`)
- Rust-based parser for `monitors.conf` and `workspaces.conf`

### Workspaces
- Visual editor grouped by monitor (physical order from `hyprctl monitors`)
- Add, remove and reorder workspaces
- Set monitor assignment, default workspace (★) and persistent flag per workspace
- Live apply via `hyprctl keyword workspace`

### Keybinds
- Full keybind editor — parser migrated from [HyprKeys](https://github.com/Jojo252511/hyprkeys)
- `$variable` resolution (reads `variables.conf`)
- Search and filter by bind type (`bind`, `binde`, `bindl` etc.)
- Create, edit and delete keybinds with automatic backup before every change
- Live reload via `hyprctl reload`
- Rust-based parser for `keybinds.conf` and `variables.conf`

### Window Rules
- App scanner — reads all `.desktop` files from system and user applications
- Assign workspace per app (dynamically loaded from `monitors.conf`, including named special workspaces)
- Set float behavior and match type (`class` or `initial_title`)
- Handles Spotify Wayland and Chromium web apps automatically
- Reads and displays existing `rules.conf` — manual rules are preserved, never duplicated
- Conflict detection — warns before saving if the same class is assigned twice
- Rust-based parser for `rules.conf` for improved performance and reliability

### General
- Keyboard layout selector — ~90 XKB layouts with live Hyprland apply
- NumLock on startup toggle
- System language (via `localectl`, requires sudo)
- Timezone (via `timedatectl`, requires sudo)

### Appearance (Caelestia shell)
- Transparency: enable/disable, surface opacity and layer opacity
- Rounding, spacing, padding and shape-deformation scales
- Animation duration scale
- Every change is written atomically to `shell.json`, with a rotating backup and undo/redo

### Typography
- Font scale plus per-style family, size, weight and italic for headline, title, body, label and monospace
- Icon font family and all four Material Symbols sizes
- Separate clock and workspace fonts

### Bar
- Reorderable bar entries (drag & drop or arrow buttons) with per-entry visibility
- Reorderable status icons (lock, audio, mic, keyboard layout, network, Bluetooth, battery)
- Workspaces: shown count, shapes/text/icons, capitalisation, window icons, labels and per-monitor mode
- Clock, tray, active-window and popout options
- Scroll actions
- Icon-rule editors for workspaces, special workspaces and window classes
- String-list editors for excluded screens, hidden tray icons and ignored window tags

### Hyprland: General
- Window layout (dwindle / master / scrolling), tearing, snapping, resize-on-border
- Gaps and border size
- Full option sets for the scrolling (niri-like), dwindle and master layouts
- Values are read from the running compositor and persisted in a generated override layer

### Hyprland: Decoration
- Rounding, rounding power, active/inactive opacity, dimming
- Blur: size, passes, xray, special workspaces, popups, input methods, optimizations
- Shadows: range, render power, sharp

### Hyprland: Input
- Keyboard layouts, variants and XKB options, repeat rate/delay, NumLock
- Mouse sensitivity, acceleration profile, scroll method/button
- Touchpad: natural scroll, tap-to-click/drag, drag lock, clickfinger, middle-button emulation, tap map, scroll factor
- Follow-mouse, special-workspace fallthrough, focus-on-close and bind scroll delay

### Hyprland: Animations
- Global animation toggle
- Bezier curve editor with per-point precision and reset-to-built-in
- Per-leaf animation editor: enable, speed, curve and style for every animation
- Changes are applied live and persisted in the generated override layer

### Hyprland: Gestures
- Workspace swipe distance, cancel ratio, speed, direction lock, create-new, forever, touch and inversion
- Additional gesture bindings (fingers, direction, action, workspace name) with reordering
- Gestures already defined in Caelestia's `gestures.lua` are left untouched

### Launcher
- Enable/hover behaviour, maximum results and wallpapers, drag threshold
- Special/action prefixes and dangerous-action toggle
- Fuzzy search per category (apps, actions, schemes, variants, wallpapers)
- Full custom action editor (name, icon, description, command, enabled, dangerous)
- Favourite and hidden application lists

### Dashboard
- Panel/media/performance/weather visibility and clock seconds
- Individual CPU/GPU/memory/storage/network/battery cards
- Media and resource refresh intervals

### Sidebar & Utilities
- Sidebar visibility, hover behaviour and thresholds
- Utilities cards, maximum toasts and full quick-toggle ordering
- Every individual toast type
- VPN provider editor (interface, connect/disconnect commands)

### Notifications & OSD
- Expiry, fullscreen policy, default/fullscreen timeouts
- Clear/expand thresholds, click actions, group preview and expanded mode
- OSD visibility, hide delay, brightness and microphone indicators

### Lock Screen
- Wallpaper background, logo recolouring and notification hiding
- Fingerprint and Howdy face unlock with retry limits
- Howdy-on-wake and session controls

### Power & Idle
- Idle timeout editor: timeout, action, return action, inhibitors and ordering
- Lock-before-sleep and audio/charging inhibitors
- Battery warning editor (level, title, message, icon, critical) and critical level

### Services
- Weather location and units; sensor, data and clock formats
- GPU type, visualiser bars, lyrics backend and default player
- Audio/brightness increments, maximum volume, smart colour scheme
- Player alias editor

### Advanced Window Rules
- Full rule editor: class/title/initial title/tag/XWayland matching
- Float, pin, centre, fullscreen, no-blur, no-shadow, no-animation, no-dim, immediate, tile, stay-focused
- Size, position, workspace, monitor, opacity, group and idle-inhibit fields
- Rule tester against all currently open windows
- Manual rules in the user rules file are preserved

### Monitor (extended)
- VRR modes (off / always / fullscreen / fullscreen + video)
- Mirror another monitor
- 8/10-bit HDR and rotation (already present) alongside the existing canvas

### Per-monitor overrides
- Dedicated page per monitor that edits `~/.config/caelestia/monitors/<output>/shell.json`
- Bar, desktop clock, wallpaper and appearance overrides with global fallback
- One-click removal of all overrides for a monitor

### Display
- Per-backlight brightness sliders (brightnessctl)
- Night light temperature control (gammastep) with persisted state
- Night light also stops externally started gammastep instances and manages its login autostart
- “Stop and reset gamma” action for stuck Hyprland gamma LUTs
- DDC/CI external monitor brightness scan and control

### Theming
- Scheme, flavour, dark/light mode and Material variant selection
- Random scheme and “from wallpaper” dynamic scheme actions
- Live palette swatches from the current Caelestia scheme

### Network
- NetworkManager device list with connect/disconnect
- VPN connection up/down
- Wi-Fi hotspot start/stop
- IPv4 method, addresses, gateway and DNS editing for the active connection

### Default Apps
- Caelestia terminal, file manager, audio and media player
- Hyprland terminal, browser, editor, file manager and audio variables
- Writes `shell.json` and `~/.config/hypr/variables.lua`, then reloads Hyprland

### Clipboard
- Browse and filter cliphist history
- Copy an entry back to the clipboard
- Delete single entries or wipe the whole history

### Capture
- Full-screen and area screenshots via grim/slurp
- Screen recording via wf-recorder with format, FPS and audio options
- Persisted output folders and recording settings

### System Services
- List, start, stop, enable and disable systemd user services

### Login Theme
- SDDM/locklike template: welcome panel, avatar shape, clock format, blur and opacity

### Raw config editor
- Built-in monospace editor for shell.json, Lua and Hyprland config files
- JSON and Lua validation before saving, automatic backups and Hyprland reload

### Global Hyprland option browser
- Search/browse all 353 options exposed by Hyprland 0.56
- Type-aware widgets (switch, number, choice, text) and reset-to-default
- Lazy row creation so opening the app stays fast

### Profiles
- Export/import a JSON profile of shell config, overrides, monitor configs, keybinds and app settings
- Path-validated imports with backups
- Reset generated Hyprland overrides or all per-monitor overrides

### Diagnostics
- Environment versions and config mode
- shell.json, advanced rules and override validation
- Hyprland config error check, Lua syntax check and integration check
- Run doctor.sh, reload Hyprland, copy a full report

### Preview mode
- Header toggle: apply changes, then keep them or auto-revert after 15 seconds

### Bluetooth
- Adapter power toggle
- Timed device discovery
- Pair, connect/disconnect, trust/untrust and forget devices

### Global search, undo and deep links
- `Ctrl+F` searches every setting (including the pre-existing pages)
- `Ctrl+Z` / `Ctrl+Shift+Z` undo and redo any change made by the new pages
- `Ctrl+R` re-reads the current page (useful after external changes)
- `caelestia-settings --page bar` (or `--page=hypr-decor`) opens a page directly

### WLAN
- Scan and connect to Wi-Fi networks via NetworkManager D-Bus API
- Secure password handling — credentials are passed over D-Bus, never exposed in process arguments (fixes issue #44)
- Password dialog for secured networks
- Disconnect from active network

### Audio
- Output device selector
- Default volume control

### Updates
- In-app system update with live progress output — no terminal popup
- Sudo password dialog (via `SUDO_ASKPASS`)
- Optional automatic reboot after update
- swaync notification on completion
- App self-update from GitHub

### Fans
- CPU and GPU temperature readout (via psutil / NVML), updated every 2 seconds
- GPU fan control: manual slider, presets (25 / 50 / 75 / 100 %), auto curve (temp-based)
- System fan PWM control via hwmon — writes directly or via sudo password dialog
- Graceful fallback when psutil or pynvml are not installed

### About
- App version from `manifest.json`
- One-click app self-update

---

## Screenshots

| Keybinds | Wallpaper | Monitor |
|----------|-----------|---------|
| ![Keybinds](https://raw.githubusercontent.com/OscarJDA/caelestia-settings-fork/main/screenshots/keybinds.png) | ![Wallpaper](https://raw.githubusercontent.com/OscarJDA/caelestia-settings-fork/main/screenshots/wallpaper.png) | ![Monitor](https://raw.githubusercontent.com/OscarJDA/caelestia-settings-fork/main/screenshots/monitor.png) |

---

## Installation

### Dependencies

For the application (Python UI + Rust parsing core):
```bash
sudo pacman -S --needed python-gobject libadwaita pamixer git python-psutil python-cairo rust networkmanager bluez-utils brightnessctl cliphist grim slurp wf-recorder ddcutil gammastep gtksourceview5
```

For Rust module development — linting/testing only, not required just to build/run the app (optional):
```bash
rustup component add clippy rust-analyzer
```

### Install

```bash
git clone https://github.com/OscarJDA/caelestia-settings-fork.git
cd caelestia-settings-fork
./install.sh
```

The installer will:
- Copy the app to `~/.local/share/caelestia-settings/`
- Build the `caelestia_core` Rust extension (via a throwaway venv + `maturin`) and install it alongside the app — this step compiles Rust code and can take a minute
- Create a `caelestia-settings` command in `~/.local/bin/`
- Add a `.desktop` entry to the app menu
- Add window rules and a `Super+I` keybind to your Hyprland config

### Uninstall

```bash
./uninstall.sh
```

Removes the installed app, the `caelestia-settings` command, the `.desktop` entry, the
app's window rules, and the `Super+I` keybind. Asks before removing your saved settings
(`~/.config/caelestia-settings/`). Leaves installed packages, the `~/.local/bin` PATH
setup, and shared Hyprland config lines (rules.conf/monitors.conf sourcing, Polkit
autostart) untouched, since those aren't exclusive to this app. Pass `-y` to skip the
confirmation prompt.

### Run without installing

`caelestia_core` is a hard dependency — build it into your environment first. Use `--system-site-packages` so the venv can also see the system `python-gobject` (PyGI) install; a plain venv won't have it and `python main.py` will fail with `ModuleNotFoundError: No module named 'gi'`. Activate the venv (rather than calling `.venv/bin/maturin` by path) so `maturin develop` reliably targets it instead of some other `.venv` it might auto-detect elsewhere:
```bash
cd caelestia-settings-fork/rust/caelestia-py
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install maturin && maturin develop
```

Then, from the same activated environment:
```bash
cd caelestia-settings-fork
python main.py
```

---

## Keyboard Shortcut

| Shortcut | Action |
|----------|--------|
| `Super + I` | Open Caelestia Settings |

To remove this shortcut, delete the following line from `~/.config/hypr/hyprland.conf`:
```
bind = SUPER, I, exec, caelestia-settings
```

---

## File Overview

```
caelestia-settings/
├── main.py                   # App entry point
├── install.sh                # Installer
├── uninstall.sh              # Uninstaller
├── app_update.sh             # Self-updater (called by the About page)
├── manifest.json             # Version info
├── ruff.toml                 # Python linter configuration
├── rust/                     # Rust workspace for parser modules
│   ├── Cargo.toml            # Rust workspace root
│   ├── caelestia-core/       # Core parser modules (pure Rust)
│   │   ├── Cargo.toml        # Package configuration
│   │   └── src/
│   │       ├── lib.rs        # Module exports
│   │       ├── config.rs     # monitors.conf and workspaces.conf parsing
│   │       ├── keybinds.rs    # keybinds.conf and variables.conf parsing
│   │       ├── rules.rs       # rules.conf windowrule parsing
│   │       ├── window_rule_conflicts.rs  # Conflict detection for window rules
│   │       └── fans.rs       # PWM percent/raw conversion for fan control
│   └── caelestia-py/          # PyO3 bindings exposing caelestia-core to Python
│       ├── Cargo.toml        # Package configuration with PyO3
│       └── src/
│           └── lib.rs        # Python module registration (caelestia_core)
└── src/
    ├── config.py             # Paths and config helpers
    ├── lang.py               # i18n (EN / DE / ES-MX — auto-detected or in-app)
    ├── safe_io.py            # Atomic writes, rotating backups, undo/redo history
    ├── settings_core.py      # Pure nested-config, Lua/conf rendering helpers
    ├── settings_engine.py    # Declarative GTK page builder + shell.json backend
    ├── settings_editors.py   # Reorderable/string/icon-rule list editors
    ├── settings_schema.py    # Page/row definitions for the declarative pages
    ├── rules_core.py         # Pure advanced window-rule rendering/matching
    ├── hypr_options_catalog.py # Generated Hyprland option catalogue (A4)
    ├── hypr_settings.py      # hyprctl reads + generated Hyprland override layer
    ├── search.py             # Global settings search index and popover
    ├── window.py             # Main window
    └── pages/
        ├── general.py        # Keyboard layout, language, timezone
        ├── appearance.py     # Caelestia appearance (transparency, scales)
        ├── typography.py     # Caelestia fonts and icon sizing
        ├── bar.py            # Caelestia bar, status icons, icon rules
        ├── launcher.py       # Launcher options, actions, favourites
        ├── dashboard.py      # Dashboard panels and refresh intervals
        ├── sidebar.py        # Sidebar, utilities, toasts and VPN providers
        ├── notifications.py  # Notifications and OSD
        ├── lock.py           # Lock screen and authentication
        ├── power.py          # Idle timeouts and battery warnings
        ├── services.py       # Weather, units, media and player aliases
        ├── hypr_general.py   # Hyprland layouts, gaps, borders
        ├── hypr_decoration.py# Hyprland rounding, opacity, blur, shadows
        ├── hypr_input.py     # Hyprland keyboard, mouse, touchpad
        ├── hypr_animations.py# Curves and per-leaf animations
        ├── hypr_gestures.py  # Swipe options and gesture bindings
        ├── monitor_overrides.py # Per-monitor shell.json overrides
        ├── bluetooth.py      # BlueZ adapter and device management
        ├── display.py        # Backlight, night light and DDC/CI
        ├── theming.py        # Caelestia colour schemes and palette
        ├── network.py        # Ethernet, VPN, hotspot and IPv4
        ├── default_apps.py   # Caelestia/Hyprland default applications
        ├── clipboard.py      # cliphist history
        ├── capture.py        # Screenshots and wf-recorder
        ├── system_services.py# systemd --user services
        ├── login_theme.py    # SDDM/locklike template
        ├── config_editor.py  # Raw validated config editor
        ├── profiles.py       # Export/import/reset
        ├── diagnostics.py    # Validation and doctor
        ├── hypr_options.py   # Searchable all-options browser
        ├── wallpaper.py      # Wallpaper browser, slideshow, favorites, clock
        ├── monitor.py        # Monitor canvas, VRR, HDR, mirror
        ├── workspaces.py     # Workspace editor
        ├── wifi.py           # Wi-Fi
        ├── audio.py          # Output, input, balance, per-app streams
        ├── window_rules.py   # App rules, advanced rules and rule tester
        ├── keybinds.py       # Keybind editor, grabber and cheat sheet
        ├── updates.py        # Updates, available packages and history
        ├── fans.py           # Fan curves, profiles and temperatures
        └── about.py          # About page
```

---

## Architecture

The application uses a hybrid Python + Rust architecture:

- **Python/GTK4**: The main application, UI, and all user interaction logic is written in Python using GTK4 and Libadwaita
- **Rust Core** (`caelestia-core`): Primary Rust crate providing all configuration file parsers (monitors.conf, workspaces.conf, keybinds.conf, variables.conf, rules.conf) and utility functions (PWM conversion, conflict detection)
- **PyO3 Bridge** (`caelestia-py`): Exposes `caelestia-core` to Python via PyO3, allowing the Python code to call Rust functions as if they were native Python extensions

This separation allows:
- Fast, reliable parsing of complex config files in Rust
- Full unit testing of parsing logic without Python dependencies
- Complete migration of configuration parsers to Rust (mandatory backend)

---

## Config Files Modified

| File | What changes |
|------|-------------|
| `~/.config/hypr/hyprland/input.conf` | Keyboard layout, NumLock |
| `~/.config/hypr/hyprland/monitors.conf` | Monitor resolution, position, rotation, scale + workspace assignments |
| `~/.config/hypr/hyprland/rules.conf` | Window rules (managed block, manual rules preserved) |
| `~/.config/hypr/hyprland/keybinds.conf` | Keybinds (with automatic `.bak` before every change) |
| `~/.config/hypr/hyprland/execs.conf` | Primary monitor (`xrandr --primary`) |
| `~/.config/caelestia/shell.json` | Desktop clock settings, taskbar visibility, appearance, typography, bar, notifications, idle, services |
| `~/.config/caelestia/monitors/<output>/shell.json` | Per-monitor overrides (bar, clock, wallpaper, appearance) |
| `~/.config/caelestia/settings-overrides.lua` | Generated Hyprland override layer (loaded from `hypr-user.lua`) |
| `~/.config/hypr/hyprland/settings-overrides.conf` | Same override layer for classic `.conf` setups |
| `~/.config/caelestia-settings/hypr_overrides.json` | Authoritative list of Hyprland overrides used to regenerate the files above |
| `~/.config/caelestia-settings/hypr_extras.json` | Animation curves, per-leaf animations and gesture bindings |
| `~/.config/caelestia-settings/advanced_rules.json` | Advanced window rules edited by the rules page |
| `~/.config/caelestia-settings/wallpaper.json` | Wallpaper favorites and slideshow settings |
| `~/.config/caelestia-settings/fans.json` | Fan curve and saved fan profile |
| `~/.config/caelestia-settings/display.json` | Night light state and temperature |
| `~/.config/caelestia-settings/capture.json` | Screenshot/recording folders, format, FPS and audio |
| `~/.config/caelestia-settings/update_history.json` | Recent update runs |
| `~/.config/caelestia-settings/window_rules.json` | Window rules cache |
| `~/.config/caelestia-settings/backups/` | Rotating backups (newest 10 per file) of every config the app writes |

---

## Language Support

The app automatically detects your system language:

| Language | Detection |
|----------|-----------|
| English | Default |
| German | `LANG=de_*` |
| Spanish (Mexico) | `LANG=es_*` |

You can override it in **General → Caelestia-settings language**
(`Automatic`, `English`, `Español (México)` or `Deutsch`). The choice is
stored in `~/.config/caelestia-settings/app.json` and is applied after
restarting the app.

---

## CI/CD

Automated testing and linting via GitHub Actions workflow (`.github/workflows/ci.yml`):

- **Python**: `ruff check` for linting (targets Python 3.12)
- **Rust**: `cargo fmt --check`, `cargo clippy --workspace --all-targets`, `cargo test --workspace` for both `caelestia-core` and `caelestia-py` crates
- **Security**: `gitleaks` for secret scanning

Triggers on push and pull request to `main` and `dev` branches.

---

## Requirements

- Arch Linux (or Arch-based distro)
- Hyprland
- [Caelestia](https://github.com/caelestia-dots/caelestia) rice
- Python 3.12+
- `python-gobject`, `libadwaita`, `pamixer`, `git`, `python-psutil`, `python-cairo`
- `rust` (required — `caelestia_core` is built from source at install time, see Installation above)
- `python-nvidia-ml-py` (optional — for GPU fan control: `yay -S python-nvidia-ml-py`)
- `yay` (for system updates)
- `nmcli` (for Wi-Fi and the Network page)
- `bluetoothctl` / `bluez-utils` (for the Bluetooth page)
- `brightnessctl`, `ddcutil` (Display page)
- `gammastep` (night light; optional)
- `cliphist` + `wl-clipboard` (Clipboard page)
- `grim`, `slurp`, `wf-recorder` (Capture page)
- `powerprofilesctl` / `power-profiles-daemon` (power profiles)
- `gtksourceview5` (optional — syntax highlighting in the Config Editor)
- `ffmpeg` (for video wallpaper thumbnails, optional)
- `mpvpaper` (for video wallpapers, optional — `yay -S mpvpaper`)
- `clippy`, `rust-analyzer` (optional — for Rust module development only, via `rustup component add`)

---

## What's New in 1.6.0

- **Phase 3 of the "total configuration" expansion**
- **All 353 Hyprland options** are searchable in a lazy, type-aware browser
- **Audio**: input selection, mute, balance and per-application streams
- **Display**: backlight, night light and DDC/CI brightness
- **Power**: power profiles, battery status and suspend/hibernate actions
- **Network**: Ethernet/VPN devices, hotspot and IPv4 editing
- **Default apps**, **clipboard history**, **screenshots/recording**, **systemd user services**
- **SDDM login theme** editor and **Caelestia theming** (scheme, flavour, mode, variant, palette)
- **Keybinds**: key grabber, conflict detection, disable/enable, submap filter and Markdown cheat sheet export
- **Window rules**: advanced editor with rule tester; manual Lua rules preserved
- **Wallpaper**: slideshow rotation and favorites
- **Fans**: configurable auto curve with hysteresis and saved profiles
- **Updates**: available package list, update history and AUR helper detection
- **Profiles**: export/import and reset of generated config
- **Diagnostics**: validation, doctor, config errors, Lua syntax and report copy
- **Raw config editor** with JSON/Lua validation and backups
- **Preview mode**: 15-second auto-revert with Keep/Revert

## What's New in 1.5.0

- **Phase 2 of the "total configuration" expansion**
- **New shell pages**: Launcher, Dashboard, Sidebar & Utilities, Notifications & OSD, Lock Screen, Power & Idle, Services
- **Hyprland animations**: bezier curve editor and per-leaf speed/curve/style editor
- **Hyprland gestures**: full swipe options plus managed gesture bindings
- **Advanced window rules**: full rule editor with XWayland/tag matching, rule tester and manual-rule preservation
- **Monitor**: VRR modes and display mirroring
- **Per-monitor overrides**: dedicated page per output with global fallback
- **Generic object-list editor**: launcher actions, VPN providers, idle timeouts, battery warnings and player aliases
- **Scrollable sidebar** to fit the larger page list

## What's New in 1.4.0

- **Phase 1 of the "total configuration" expansion**
- **Declarative settings engine**: schema-driven pages with shared widgets, search and undo
- **Safe writes**: atomic file replacement plus rotating backups (`~/.config/caelestia-settings/backups`)
- **Undo/redo**: header buttons and `Ctrl+Z` / `Ctrl+Shift+Z`
- **Global search**: `Ctrl+F`, including the pre-existing pages
- **Deep links**: `caelestia-settings --page bar`
- **New pages**: Appearance, Typography, Bar, Hyprland General/Decoration/Input, Bluetooth
- **Hyprland override layer**: generated Lua or `.conf` file, applied live through `hyprctl eval`/`keyword`
- **Caelestia shell settings**: transparency, scaling, all fonts and icon sizes, complete bar configuration
- **Bluetooth**: scan, pair, connect, trust and forget devices

## What's New in 1.3.0

- **Rust modules**: `window_rule_conflicts.rs` (conflict detection) and `fans.rs` (PWM percentage conversion) are now complete — fully tested (38/38 tests passing), clippy/fmt clean
- **PyO3 bindings**: New `caelestia-py` crate exposes all `caelestia-core` parsing and utility functions to Python as the `caelestia_core` extension module
- **Self-update fix**: `app_update.sh` now explicitly pins the `main` branch instead of following GitHub's default branch (previously pulled from `dev` by mistake)

## Roadmap

- [x] Monitor canvas with drag-and-drop
- [x] Workspace editor
- [x] Keybind editor
- [x] Window rules app scanner
- [x] Wallpaper browser with video support
- [x] Desktop clock settings
- [x] In-app update UI
- [x] English / German / Spanish (Mexico) language support
- [x] Fan & temperature monitoring with GPU fan control
- [x] Rust module for monitors.conf parsing
- [x] Rust module for keybinds.conf parsing
- [x] Rust module for rules.conf parsing
- [x] Rust module for window-rule conflict detection
- [x] Rust module for fan PWM percentage conversion
- [x] CI pipeline with Python and Rust linting/tests
- [x] PyO3 bindings for Rust to Python integration (via `caelestia-py`)
- [x] Integrate Rust parsers in fans.py, keybinds.py, config.py (monitors/rules parsing), window_rules.py
- [x] `caelestia_core` built and installed automatically by `install.sh` — no more optional Python fallback, Rust is a hard dependency
- [x] Caelestia appearance, typography and bar configuration
- [x] Hyprland general/decoration/input configuration with a managed override layer
- [x] Global settings search, undo/redo and `--page` deep links
- [x] Bluetooth device management
- [x] Launcher, dashboard, sidebar/utilities, notifications, lock, power and services configuration
- [x] Hyprland animation and gesture editors
- [x] Advanced window rules with rule tester
- [x] Monitor VRR, HDR and mirroring
- [x] Per-monitor shell overrides
- [x] Full Hyprland option browser
- [x] Audio input, balance and per-app streams
- [x] Backlight, night light and DDC/CI
- [x] Power profiles, network extras and default applications
- [x] Clipboard, capture and systemd user services
- [x] Theming and SDDM login theme editors
- [x] Keybind grabber, conflicts and cheat sheet export
- [x] Wallpaper slideshow/favorites, fan curves/profiles and update history
- [x] Profiles, diagnostics, raw config editor and preview mode
- [ ] Arbitrary accent colour selection (Caelestia generates schemes from wallpapers/named palettes)

---

## Maintainer

**OscarJDA** — [GitHub](https://github.com/OscarJDA)

Original project by **Jojo252511** — [GitHub](https://github.com/Jojo252511) — [Ko-fi](https://ko-fi.com/jojo2511). This fork keeps the original MIT license and attribution.

Made for the [Caelestia](https://github.com/caelestia-dots/caelestia) ecosystem.
