pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.I18n
import qs.components
import qs.services

// Shared frame for every desktop widget. Widgets declare their rows as
// children; they are reparented into the body layout.
StyledRect {
    id: root

    property var widgetConfig: ({})
    property var globalConfig: ({})
    property string title
    property string iconName: "widgets"
    property bool showHeader: true
    property real cardWidth: 300
    property bool interactive: false
    signal clicked()

    readonly property var opts: (widgetConfig && widgetConfig.options) ? widgetConfig.options : ({})
    readonly property real widgetScale: (widgetConfig && widgetConfig.scale) ? widgetConfig.scale : 1
    readonly property string style: globalConfig.cardStyle ?? "material"
    readonly property real cardOpacity: globalConfig.opacity ?? 1
    readonly property bool minimal: style === "minimal"
    readonly property real padding: minimal ? 0 : Tokens.padding.large * widgetScale
    readonly property color accentColour: root.resolveAccent()
    readonly property string language: Tr.language

    default property alias content: body.data

    function tr(en: string, es: string, de: string): string {
        if (root.language.startsWith("es"))
            return es;
        if (root.language.startsWith("de"))
            return de;
        return en;
    }

    function resolveAccent(): color {
        const choice = (root.opts && root.opts.accent) ? root.opts.accent : (root.globalConfig.accent ?? "auto");
        switch (choice) {
        case "secondary":
            return Colours.palette.m3secondary;
        case "tertiary":
            return Colours.palette.m3tertiary;
        case "error":
            return Colours.palette.m3error;
        default:
            return Colours.palette.m3primary;
        }
    }

    implicitWidth: Math.round(root.cardWidth * root.widgetScale)
    implicitHeight: Math.round(layout.implicitHeight + root.padding * 2)
    color: {
        if (root.minimal)
            return "transparent";
        if (root.style === "glass")
            return Qt.alpha(Colours.tPalette.m3surfaceContainer, root.cardOpacity * 0.62);
        return Qt.alpha(Colours.tPalette.m3surfaceContainer, root.cardOpacity);
    }
    radius: root.minimal ? 0 : Tokens.rounding.extraLarge * root.widgetScale
    border.width: root.style === "glass" ? 1 : 0
    border.color: Qt.alpha(Colours.palette.m3outline, 0.25)

    property MouseArea clickArea: MouseArea {
        anchors.fill: parent
        enabled: root.interactive
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    ColumnLayout {
        id: layout

        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.padding
        spacing: Tokens.spacing.medium * root.widgetScale

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale
            visible: root.showHeader && root.title !== ""

            MaterialIcon {
                text: root.iconName
                color: root.accentColour
                fontStyle: Tokens.font.icon.builders.medium.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                text: root.title
                font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }
        }

        ColumnLayout {
            id: body

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale
        }
    }
}
