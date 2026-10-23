pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Quick actions", "Acciones rápidas", "Schnellaktionen")
    iconName: "bolt"
    cardWidth: 300

    property string pending: ""
    property string lastAction: ""

    readonly property var actionList: {
        const raw = (root.opts.actions ?? "").split(",");
        const result = [];
        for (const item of raw) {
            const id = item.trim();
            if (id !== "" && root.actionInfo(id) !== null)
                result.push(id);
        }
        return result;
    }

    readonly property var columns: Math.max(2, Math.min(6, Number(root.opts.columns) || 4))

    function actionInfo(id: string): var {
        switch (id) {
        case "lock":
            return { icon: "lock", label: root.tr("Lock", "Bloquear", "Sperren"), confirm: false };
        case "suspend":
            return { icon: "bedtime", label: root.tr("Suspend", "Suspender", "Bereitschaft"), confirm: true };
        case "reboot":
            return { icon: "restart_alt", label: root.tr("Reboot", "Reiniciar", "Neustart"), confirm: true };
        case "shutdown":
            return { icon: "power_settings_new", label: root.tr("Shut down", "Apagar", "Herunterfahren"), confirm: true };
        case "logout":
            return { icon: "logout", label: root.tr("Log out", "Cerrar sesión", "Abmelden"), confirm: true };
        case "screenshot":
            return { icon: "screenshot_monitor", label: root.tr("Screenshot", "Captura", "Bildschirmfoto"), confirm: false };
        case "record":
            return { icon: "screen_record", label: root.tr("Record", "Grabar", "Aufnehmen"), confirm: false };
        case "dnd":
            return { icon: Notifs.dnd ? "notifications_off" : "notifications", label: Notifs.dnd ? root.tr("DND on", "No molestar", "Nicht stören") : root.tr("DND off", "Permitir avisos", "Störungen aus"), confirm: false };
        case "gamemode":
            return { icon: "sports_esports", label: root.tr("Game mode", "Modo juego", "Spielmodus"), confirm: false };
        case "clipboard":
            return { icon: "content_paste", label: root.tr("Clipboard", "Portapapeles", "Zwischenablage"), confirm: false };
        default:
            return null;
        }
    }

    function run(id: string): void {
        const info = root.actionInfo(id);
        if (info === null)
            return;

        if (info.confirm && root.opts.confirm !== false && root.pending !== id) {
            root.pending = id;
            pendingTimer.restart();
            return;
        }

        root.pending = "";
        root.lastAction = id;

        switch (id) {
        case "lock":
            Quickshell.execDetached(["caelestia", "shell", "lock", "lock"]);
            break;
        case "suspend":
            Quickshell.execDetached(["systemctl", "suspend"]);
            break;
        case "reboot":
            Quickshell.execDetached(["systemctl", "reboot"]);
            break;
        case "shutdown":
            Quickshell.execDetached(["systemctl", "poweroff"]);
            break;
        case "logout":
            Quickshell.execDetached(["hyprctl", "dispatch", "exit"]);
            break;
        case "screenshot":
            Quickshell.execDetached(["caelestia", "screenshot"]);
            break;
        case "record":
            Quickshell.execDetached(["caelestia", "record"]);
            break;
        case "dnd":
            Notifs.dnd = !Notifs.dnd;
            break;
        case "gamemode":
            GameMode.enabled = !GameMode.enabled;
            break;
        case "clipboard":
            Quickshell.execDetached(["caelestia", "clipboard"]);
            break;
        }
    }

    Timer {
        id: pendingTimer

        interval: 3000
        onTriggered: root.pending = ""
    }

    GridLayout {
        Layout.fillWidth: true
        columns: root.columns
        rowSpacing: Tokens.spacing.small * root.widgetScale
        columnSpacing: Tokens.spacing.small * root.widgetScale

        Repeater {
            model: root.actionList

            delegate: StyledRect {
                id: button

                required property var modelData

                readonly property var info: root.actionInfo(modelData)
                readonly property bool armed: root.pending === modelData
                readonly property bool activeToggle: (modelData === "dnd" && Notifs.dnd) || (modelData === "gamemode" && GameMode.enabled)

                Layout.fillWidth: true
                implicitHeight: 54 * root.widgetScale
                radius: Tokens.rounding.large * root.widgetScale
                color: armed || activeToggle ? Qt.alpha(root.accentColour, 0.22) : Colours.tPalette.m3surfaceContainerHigh

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2 * root.widgetScale

                    MaterialIcon {
                        Layout.alignment: Qt.AlignHCenter
                        text: button.info.icon
                        color: button.armed || button.activeToggle ? root.accentColour : Colours.palette.m3onSurface
                        fontStyle: Tokens.font.icon.builders.medium.scale(root.widgetScale).build()
                    }

                    StyledText {
                        Layout.alignment: Qt.AlignHCenter
                        text: button.armed ? root.tr("Again", "Otra vez", "Erneut") : button.info.label
                        color: button.armed ? root.accentColour : Colours.palette.m3onSurfaceVariant
                        font: Tokens.font.label.builders.small.scale(0.9 * root.widgetScale).build()
                        elide: Text.ElideRight
                    }
                }

                StateLayer {
                    radius: Tokens.rounding.large * root.widgetScale
                    onClicked: root.run(button.modelData)
                }
            }
        }
    }
}
