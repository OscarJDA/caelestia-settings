pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.I18n
import Caelestia.Services
import qs.components
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("System", "Sistema", "System")
    iconName: "monitor_heart"
    cardWidth: 300

    readonly property bool compact: root.opts.compact === true
    readonly property bool showBars: root.opts.showBars !== false && !root.compact
    readonly property bool showTemps: root.opts.showTemps !== false && !root.compact

    ServiceRef {
        service: Cpu
    }

    ServiceRef {
        service: Gpu
    }

    ServiceRef {
        service: Memory
    }

    ServiceRef {
        service: Storage
    }

    ServiceRef {
        service: NetworkUsage
    }

    WidgetStat {
        visible: root.opts.showCpu !== false
        iconName: "memory"
        label: root.tr("CPU", "CPU", "CPU")
        value: Cpu.percentage
        detail: root.showTemps ? Units.formatSensorTemp(Cpu.temperature) : ""
        showBar: root.showBars
        accent: Colours.palette.m3primary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showGpu !== false && Gpu.type !== GpuType.None
        iconName: "desktop_windows"
        label: root.tr("GPU", "GPU", "GPU")
        value: Gpu.percentage
        detail: root.showTemps ? Units.formatSensorTemp(Gpu.temperature) : ""
        showBar: root.showBars
        accent: Colours.palette.m3secondary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showMemory !== false
        iconName: "memory_alt"
        label: root.tr("Memory", "Memoria", "Arbeitsspeicher")
        value: Memory.percentage
        detail: root.compact ? "" : Units.formatKibUsage(Memory.used, Memory.total)
        showBar: root.showBars
        accent: Colours.palette.m3tertiary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showStorage !== false
        iconName: "hard_drive"
        label: root.tr("Storage", "Almacenamiento", "Speicher")
        value: Storage.percentage
        detail: root.compact ? "" : (Storage.primaryDisk ? Units.formatKibUsage(Storage.primaryDisk.used, Storage.primaryDisk.total) : "--")
        showBar: root.showBars
        accent: Colours.palette.m3secondary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showNetwork !== false
        iconName: "swap_vert"
        label: root.tr("Network", "Red", "Netzwerk")
        valueText: "↓ " + Units.formatBytes(NetworkUsage.downloadSpeed ?? 0, true)
        detail: root.compact ? "" : ("↑ " + Units.formatBytes(NetworkUsage.uploadSpeed ?? 0, true))
        showBar: false
        accent: Colours.palette.m3primary
        widgetScale: root.widgetScale
    }
}
