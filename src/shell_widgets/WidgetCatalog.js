.pragma library

// Metadata for every desktop widget type. The shell uses this to resolve the
// QML component and to merge missing options; Caelestia Settings mirrors it in
// src/widget_catalog.py.

const TYPES = {
    clock: {
        name: "Clock",
        icon: "schedule",
        width: 300,
        corner: "top-center",
        options: {
            showDate: true,
            showSeconds: false,
            showWeekday: true,
            dateFormat: "long",
            format: "system"
        }
    },
    worldclock: {
        name: "World clock",
        icon: "public",
        width: 280,
        corner: "middle-left",
        options: {
            cities: "Tokyo:+9,London:+0,New York:-5",
            format: "system",
            showOffset: true
        }
    },
    moon: {
        name: "Moon phase",
        icon: "dark_mode",
        width: 260,
        corner: "middle-left",
        options: {
            hemisphere: "north",
            showName: true,
            showIllumination: true
        }
    },
    calendar: {
        name: "Calendar",
        icon: "calendar_month",
        width: 300,
        corner: "bottom-right",
        options: {
            weekNumbers: false,
            showWeekdays: true,
            startOfWeek: "locale"
        }
    },
    agenda: {
        name: "Agenda",
        icon: "event_note",
        width: 320,
        corner: "middle-right",
        options: {
            path: "~/.config/caelestia-settings/agenda.ics",
            maxEvents: 5,
            daysAhead: 14,
            showLocation: true
        }
    },
    weather: {
        name: "Weather",
        icon: "cloud",
        width: 300,
        corner: "bottom-right",
        options: {
            showFeelsLike: true,
            showHumidity: true,
            showWind: true,
            showSun: true,
            showCity: true
        }
    },
    forecast: {
        name: "Forecast",
        icon: "thermostat",
        width: 320,
        corner: "bottom-right",
        options: {
            mode: "hourly",
            count: 6,
            showPrecip: true
        }
    },
    airquality: {
        name: "Air quality",
        icon: "air",
        width: 300,
        corner: "bottom-right",
        options: {
            pollutant: "aqi",
            showPm: true
        }
    },
    system: {
        name: "System monitor",
        icon: "monitor_heart",
        width: 300,
        corner: "top-right",
        options: {
            showCpu: true,
            showGpu: true,
            showMemory: true,
            showStorage: true,
            showNetwork: true,
            showBars: true,
            showTemps: true,
            compact: false
        }
    },
    storage: {
        name: "Storage",
        icon: "hard_drive",
        width: 300,
        corner: "middle-right",
        options: {
            maxDisks: 4,
            showBars: true,
            showFree: true
        }
    },
    network: {
        name: "Network",
        icon: "swap_vert",
        width: 320,
        corner: "top-right",
        options: {
            showSparkline: true,
            showTotals: true,
            showSsid: true,
            showVpn: true
        }
    },
    battery: {
        name: "Battery",
        icon: "battery_full",
        width: 280,
        corner: "bottom-center",
        options: {
            showTime: true,
            showHealth: false,
            showProfile: true,
            lowThreshold: 20
        }
    },
    sensors: {
        name: "Sensors",
        icon: "device_thermostat",
        width: 300,
        corner: "middle-right",
        options: {
            maxItems: 4,
            showTemps: true,
            showFans: true
        }
    },
    processes: {
        name: "Top processes",
        icon: "list_alt",
        width: 320,
        corner: "middle-right",
        options: {
            count: 5,
            sortBy: "cpu"
        }
    },
    sysinfo: {
        name: "System information",
        icon: "info",
        width: 300,
        corner: "middle-left",
        options: {
            showHost: true,
            showKernel: true,
            showUptime: true,
            showDevice: true,
            showCpu: true,
            showGpu: false,
            showWm: true
        }
    },
    media: {
        name: "Media",
        icon: "music_note",
        width: 340,
        corner: "bottom-left",
        options: {
            showArt: true,
            showAlbum: true,
            showControls: true,
            showProgress: true,
            hideWhenStopped: false
        }
    },
    lyrics: {
        name: "Lyrics",
        icon: "lyrics",
        width: 360,
        corner: "bottom-left",
        options: {
            lines: 3,
            centered: true,
            showTitle: false
        }
    },
    visualiser: {
        name: "Audio visualiser",
        icon: "graphic_eq",
        width: 320,
        corner: "bottom-center",
        options: {
            widthScale: 1,
            heightScale: 1,
            style: "bars",
            colorMode: "artwork",
            bars: 48,
            mirror: true,
            showWhenIdle: false
        }
    },
    quickactions: {
        name: "Quick actions",
        icon: "bolt",
        width: 300,
        corner: "middle-right",
        options: {
            actions: "lock,suspend,reboot,shutdown,screenshot,record,dnd",
            columns: 4,
            confirm: true
        }
    },
    launcher: {
        name: "App launcher",
        icon: "apps",
        width: 320,
        corner: "middle-left",
        options: {
            apps: "",
            columns: 4,
            showNames: false
        }
    },
    notes: {
        name: "Notes",
        icon: "sticky_note_2",
        width: 300,
        corner: "middle-left",
        options: {
            path: "~/.config/caelestia-settings/notes.txt",
            maxLines: 6,
            openOnClick: true
        }
    },
    pomodoro: {
        name: "Pomodoro",
        icon: "timer",
        width: 260,
        corner: "middle-left",
        options: {
            workMinutes: 25,
            shortBreakMinutes: 5,
            longBreakMinutes: 15,
            longBreakEvery: 4,
            autoStartBreaks: false
        }
    },
    stopwatch: {
        name: "Stopwatch",
        icon: "av_timer",
        width: 260,
        corner: "middle-left",
        options: {
            showHundredths: true
        }
    },
    notifications: {
        name: "Notifications",
        icon: "notifications",
        width: 320,
        corner: "middle-right",
        options: {
            maxItems: 4,
            showAppName: true,
            showTime: true
        }
    }
};

const COMPONENTS = {
    clock: "WidgetClock.qml",
    worldclock: "WidgetWorldClock.qml",
    moon: "WidgetMoon.qml",
    calendar: "WidgetCalendar.qml",
    agenda: "WidgetAgenda.qml",
    weather: "WidgetWeather.qml",
    forecast: "WidgetForecast.qml",
    airquality: "WidgetAirQuality.qml",
    system: "WidgetSystem.qml",
    storage: "WidgetStorage.qml",
    network: "WidgetNetwork.qml",
    battery: "WidgetBattery.qml",
    sensors: "WidgetSensors.qml",
    processes: "WidgetProcesses.qml",
    sysinfo: "WidgetSysInfo.qml",
    media: "WidgetMedia.qml",
    lyrics: "WidgetLyrics.qml",
    visualiser: "WidgetVisualiser.qml",
    quickactions: "WidgetQuickActions.qml",
    launcher: "WidgetLauncher.qml",
    notes: "WidgetNotes.qml",
    pomodoro: "WidgetPomodoro.qml",
    stopwatch: "WidgetStopwatch.qml",
    notifications: "WidgetNotifications.qml"
};

function has(type) {
    return Object.prototype.hasOwnProperty.call(TYPES, type);
}

function meta(type) {
    return TYPES[type] ?? null;
}

function componentFor(type) {
    return COMPONENTS[type] ?? "";
}

function optionsFor(type) {
    return Object.assign({}, TYPES[type]?.options ?? {});
}

function defaults(type) {
    const info = TYPES[type];
    if (!info)
        return null;
    return {
        type: type,
        enabled: true,
        corner: info.corner,
        order: 0,
        scale: 1,
        options: Object.assign({}, info.options)
    };
}

function widthFor(type) {
    return TYPES[type]?.width ?? 300;
}

function label(type) {
    return TYPES[type]?.name ?? type;
}

function iconFor(type) {
    return TYPES[type]?.icon ?? "widgets";
}
