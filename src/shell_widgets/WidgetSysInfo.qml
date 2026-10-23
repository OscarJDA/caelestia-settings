pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.Services
import qs.components
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("System information", "Información del sistema", "Systeminformationen")
    iconName: "info"
    cardWidth: 300

    WidgetStat {
        visible: root.opts.showHost !== false
        iconName: "dns"
        label: root.tr("Host", "Equipo", "Host")
        valueText: SysInfo.hostname || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showDevice !== false
        iconName: "laptop"
        label: root.tr("Device", "Dispositivo", "Gerät")
        valueText: SysInfo.device || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showKernel !== false
        iconName: "terminal"
        label: root.tr("Kernel", "Kernel", "Kernel")
        valueText: SysInfo.kernel || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showUptime !== false
        iconName: "schedule"
        label: root.tr("Uptime", "Tiempo encendido", "Laufzeit")
        valueText: SysInfo.uptimeShort || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showCpu !== false
        iconName: "memory"
        label: root.tr("CPU", "CPU", "CPU")
        valueText: Cpu.name || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showGpu === true
        iconName: "desktop_windows"
        label: root.tr("GPU", "GPU", "GPU")
        valueText: Gpu.name || "--"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showWm !== false
        iconName: "window"
        label: root.tr("Session", "Sesión", "Sitzung")
        valueText: (SysInfo.wm || "") + (SysInfo.shell ? " · " + SysInfo.shell : "")
        showBar: false
        widgetScale: root.widgetScale
    }
}
