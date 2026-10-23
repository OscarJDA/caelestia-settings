pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("Battery", "Batería", "Akku")
    iconName: Icons.getBatteryIcon(battery.percentage, battery.charging)
    cardWidth: 280

    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: battery.isLaptopBattery
    readonly property real level: Math.max(0, Math.min(1, battery.percentage ?? 0))
    readonly property bool charging: [UPowerDeviceState.Charging, UPowerDeviceState.FullyCharged, UPowerDeviceState.PendingCharge].includes(battery.state)
    readonly property bool low: root.level * 100 <= (root.opts.lowThreshold ?? 20)
    readonly property color levelColour: root.charging ? Colours.palette.m3tertiary : (root.low ? Colours.palette.m3error : root.accentColour)

    property string profile: ""

    function stateText(): string {
        switch (root.battery.state) {
        case UPowerDeviceState.Charging:
            return root.tr("Charging", "Cargando", "Wird geladen");
        case UPowerDeviceState.FullyCharged:
            return root.tr("Full", "Completa", "Voll");
        case UPowerDeviceState.Discharging:
            return root.tr("Discharging", "Descargando", "Entlädt");
        case UPowerDeviceState.PendingCharge:
            return root.tr("Pending charge", "Carga pendiente", "Laden ausstehend");
        case UPowerDeviceState.PendingDischarge:
            return root.tr("Pending discharge", "Descarga pendiente", "Entladen ausstehend");
        default:
            return root.tr("Unknown", "Desconocido", "Unbekannt");
        }
    }

    function timeText(): string {
        const seconds = root.charging ? root.battery.timeToFull : root.battery.timeToEmpty;
        if (!seconds || seconds <= 0)
            return "";
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (hours > 0)
            return hours + " h " + minutes + " min";
        return minutes + " min";
    }

    function profileLabel(value: string): string {
        switch (value) {
        case "power-saver":
            return root.tr("Power saver", "Ahorro", "Energiesparen");
        case "balanced":
            return root.tr("Balanced", "Equilibrado", "Ausgeglichen");
        case "performance":
            return root.tr("Performance", "Rendimiento", "Leistung");
        default:
            return value;
        }
    }

    function cycleProfile(): void {
        const values = ["power-saver", "balanced", "performance"];
        const index = values.indexOf(root.profile);
        const next = values[(index + 1) % values.length];
        Quickshell.execDetached(["powerprofilesctl", "set", next]);
        root.profile = next;
    }

    Process {
        id: profileProcess

        command: ["powerprofilesctl", "get"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: root.profile = text.trim()
        }
    }

    Timer {
        interval: 30000
        running: root.opts.showProfile !== false
        repeat: true
        triggeredOnStart: true
        onTriggered: profileProcess.running = true
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.medium * root.widgetScale

        Item {
            implicitWidth: 74 * root.widgetScale
            implicitHeight: 74 * root.widgetScale

            CircularProgress {
                anchors.fill: parent
                value: root.level
                strokeWidth: Tokens.padding.small * root.widgetScale
                fgColour: root.levelColour
            }

            StyledText {
                anchors.centerIn: parent
                text: Math.round(root.level * 100) + "%"
                color: root.levelColour
                font: Tokens.font.title.builders.medium.scale(root.widgetScale).build()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            StyledText {
                Layout.fillWidth: true
                text: root.hasBattery ? root.stateText() : root.tr("No battery", "Sin batería", "Kein Akku")
                font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.opts.showTime !== false && root.timeText() !== ""
                text: root.timeText()
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.opts.showHealth === true && root.hasBattery
                text: root.tr("Health", "Salud", "Gesundheit") + ": " + Math.round((root.battery.healthPercentage ?? 0) * 100) + "%"
                color: Colours.palette.m3outline
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        visible: root.opts.showProfile !== false
        spacing: Tokens.spacing.small

        MaterialIcon {
            text: "speed"
            color: root.accentColour
            fontStyle: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
        }

        StyledText {
            Layout.fillWidth: true
            text: root.tr("Power profile", "Perfil de energía", "Energieprofil")
            font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        }

        StyledText {
            text: root.profileLabel(root.profile)
            color: root.accentColour
            font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        }

        WidgetIconButton {
            icon: "swap_horiz"
            widgetScale: root.widgetScale
            enabled: root.profile !== ""
            onClicked: root.cycleProfile()
        }
    }
}
