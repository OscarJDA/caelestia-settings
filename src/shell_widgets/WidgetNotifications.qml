pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("Notifications", "Notificaciones", "Benachrichtigungen")
    iconName: Notifs.dnd ? "notifications_off" : "notifications"
    cardWidth: 320

    readonly property int maxItems: Math.max(1, Math.min(12, Number(root.opts.maxItems) || 4))
    readonly property var items: (Notifs.notClosed ?? []).slice(0, root.maxItems)

    Repeater {
        model: root.items

        delegate: RowLayout {
            id: entry

            required property var modelData

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale

            MaterialIcon {
                text: Icons.getNotifIcon(entry.modelData.summary ?? "", entry.modelData.urgency ?? 0)
                color: root.accentColour
                fontStyle: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    Layout.fillWidth: true
                    text: entry.modelData.summary || entry.modelData.appName || ""
                    font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: (entry.modelData.body ?? "") !== ""
                    text: entry.modelData.body ?? ""
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                    elide: Text.ElideRight
                    maximumLineCount: 1
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: root.opts.showAppName !== false || root.opts.showTime !== false
                    text: [root.opts.showAppName !== false ? (entry.modelData.appName ?? "") : "", root.opts.showTime !== false ? (entry.modelData.timeStr ?? "") : ""].filter(part => part !== "").join(" · ")
                    color: Colours.palette.m3outline
                    font: Tokens.font.label.builders.small.scale(0.9 * root.widgetScale).build()
                    elide: Text.ElideRight
                }
            }

            WidgetIconButton {
                icon: "close"
                widgetScale: root.widgetScale
                onClicked: entry.modelData.close()
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.items.length === 0
        text: root.tr("All caught up", "Todo al día", "Alles erledigt")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
