pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services
import qs.utils

ColumnLayout {
    id: root

    property string iconName
    property string label
    property real value: -1
    property string valueText
    property string detail
    property color accent: Colours.palette.m3primary
    property bool showBar: true
    property real widgetScale: 1

    Layout.fillWidth: true
    spacing: Tokens.spacing.extraSmall * root.widgetScale

    Item {
        Layout.fillWidth: true
        implicitHeight: Math.max(labelText.implicitHeight, valueLabel.implicitHeight)

        MaterialIcon {
            id: icon

            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            visible: root.iconName !== ""
            text: root.iconName
            color: root.accent
            fontStyle: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
        }

        StyledText {
            id: valueLabel

            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, parent.width * (icon.visible ? 0.5 : 0.62))
            text: root.value >= 0 ? Strings.percentOne(root.value) : (root.valueText ?? "")
            color: root.accent
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
        }

        StyledText {
            id: labelText

            anchors.left: icon.visible ? icon.right : parent.left
            anchors.leftMargin: icon.visible ? Tokens.spacing.small * root.widgetScale : 0
            anchors.right: valueLabel.left
            anchors.rightMargin: Tokens.spacing.small * root.widgetScale
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
            elide: Text.ElideRight
        }
    }

    StyledProgressBar {
        Layout.fillWidth: true
        visible: root.showBar && root.value >= 0
        value: Math.max(0, Math.min(1, root.value))
        implicitHeight: Tokens.padding.extraSmall * 2 * root.widgetScale
        fgColour: root.accent
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.detail !== ""
        text: root.detail ?? ""
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        elide: Text.ElideRight
    }
}
