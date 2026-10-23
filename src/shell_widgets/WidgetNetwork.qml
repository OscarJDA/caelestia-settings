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

    title: tr("Network", "Red", "Netzwerk")
    iconName: "swap_vert"
    cardWidth: 320

    readonly property string ssid: Nmcli.active?.ssid ?? Nmcli.activeConnection ?? ""

    ServiceRef {
        service: NetworkUsage
    }

    WidgetSparkline {
        Layout.fillWidth: true
        visible: root.opts.showSparkline !== false
        buffer: NetworkUsage.downloadBuffer
        buffer2: NetworkUsage.uploadBuffer
        lineColour: Colours.palette.m3tertiary
        lineColour2: Colours.palette.m3secondary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showSsid !== false && root.ssid !== ""
        iconName: Nmcli.wifiEnabled ? "wifi" : "wifi_off"
        label: root.ssid
        valueText: Nmcli.isConnected ? root.tr("Connected", "Conectado", "Verbunden") : root.tr("Offline", "Sin conexión", "Offline")
        showBar: false
        accent: Nmcli.isConnected ? Colours.palette.m3tertiary : Colours.palette.m3error
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showVpn !== false && VPN.connected
        iconName: "vpn_lock"
        label: VPN.providerName
        valueText: root.tr("VPN", "VPN", "VPN")
        showBar: false
        accent: Colours.palette.m3secondary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        iconName: "download"
        label: root.tr("Download", "Descarga", "Download")
        valueText: Units.formatBytes(NetworkUsage.downloadSpeed ?? 0, true)
        showBar: false
        accent: Colours.palette.m3tertiary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        iconName: "upload"
        label: root.tr("Upload", "Subida", "Upload")
        valueText: Units.formatBytes(NetworkUsage.uploadSpeed ?? 0, true)
        showBar: false
        accent: Colours.palette.m3secondary
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showTotals !== false
        iconName: "data_usage"
        label: root.tr("Session", "Sesión", "Sitzung")
        valueText: "↓ " + Units.formatBytes(NetworkUsage.downloadTotal ?? 0) + "  ↑ " + Units.formatBytes(NetworkUsage.uploadTotal ?? 0)
        showBar: false
        accent: Colours.palette.m3primary
        widgetScale: root.widgetScale
    }
}
