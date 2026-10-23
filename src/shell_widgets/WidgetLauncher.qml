pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Apps", "Aplicaciones", "Apps")
    iconName: "apps"
    cardWidth: 320

    readonly property int columns: Math.max(2, Math.min(8, Number(root.opts.columns) || 4))
    readonly property bool showNames: root.opts.showNames === true

    readonly property var entries: {
        const all = [...DesktopEntries.applications.values];
        const raw = (root.opts.apps ?? "").trim();
        let picked;
        if (raw === "") {
            picked = all.sort((a, b) => a.name.localeCompare(b.name)).slice(0, root.columns * 2);
        } else {
            const ids = raw.split(",").map(id => id.trim()).filter(id => id !== "");
            picked = ids.map(id => all.find(entry => entry.id === id)).filter(entry => entry !== undefined);
        }
        return picked;
    }

    GridLayout {
        Layout.fillWidth: true
        columns: root.columns
        rowSpacing: Tokens.spacing.small * root.widgetScale
        columnSpacing: Tokens.spacing.small * root.widgetScale

        Repeater {
            model: root.entries

            delegate: StyledRect {
                id: tile

                required property var modelData

                Layout.fillWidth: true
                implicitHeight: (root.showNames ? 62 : 48) * root.widgetScale
                radius: Tokens.rounding.large * root.widgetScale
                color: Colours.tPalette.m3surfaceContainerHigh

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2 * root.widgetScale

                    IconImage {
                        Layout.alignment: Qt.AlignHCenter
                        implicitSize: 26 * root.widgetScale
                        source: Quickshell.iconPath(tile.modelData.icon, "image-missing")
                        asynchronous: true
                    }

                    StyledText {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.maximumWidth: tile.width - 8
                        visible: root.showNames
                        text: tile.modelData.name
                        horizontalAlignment: Text.AlignHCenter
                        font: Tokens.font.label.builders.small.scale(0.9 * root.widgetScale).build()
                        elide: Text.ElideRight
                    }
                }

                StateLayer {
                    radius: Tokens.rounding.large * root.widgetScale
                    onClicked: tile.modelData.execute()
                }
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.entries.length === 0
        text: root.tr("No applications found", "No se encontraron aplicaciones", "Keine Anwendungen gefunden")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
