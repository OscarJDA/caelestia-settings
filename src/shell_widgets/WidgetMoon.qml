pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Moon", "Luna", "Mond")
    iconName: root.moonIcon()
    cardWidth: 260

    property date now: new Date()

    readonly property real phase: root.currentPhase()
    readonly property real illumination: (1 - Math.cos(2 * Math.PI * root.phase)) / 2
    readonly property bool southern: root.opts.hemisphere === "south"

    function currentPhase(): real {
        const newMoon = Date.UTC(2000, 0, 6, 18, 14);
        const synodic = 29.530588853;
        const days = (root.now.getTime() - newMoon) / 86400000;
        let value = (days % synodic) / synodic;
        if (value < 0)
            value += 1;
        return value;
    }

    function phaseName(): string {
        const p = root.phase;
        if (p < 0.03 || p > 0.97)
            return root.tr("New moon", "Luna nueva", "Neumond");
        if (p < 0.22)
            return root.tr("Waxing crescent", "Luna creciente", "Zunehmende Sichel");
        if (p < 0.28)
            return root.tr("First quarter", "Cuarto creciente", "Erstes Viertel");
        if (p < 0.47)
            return root.tr("Waxing gibbous", "Gibosa creciente", "Zunehmender Mond");
        if (p < 0.53)
            return root.tr("Full moon", "Luna llena", "Vollmond");
        if (p < 0.72)
            return root.tr("Waning gibbous", "Gibosa menguante", "Abnehmender Mond");
        if (p < 0.78)
            return root.tr("Last quarter", "Cuarto menguante", "Letztes Viertel");
        return root.tr("Waning crescent", "Luna menguante", "Abnehmende Sichel");
    }

    function moonIcon(): string {
        const p = root.phase;
        if (p < 0.03 || p > 0.97)
            return "dark_mode";
        if (p < 0.22)
            return "brightness_3";
        if (p < 0.28)
            return "contrast";
        if (p < 0.47)
            return "brightness_7";
        if (p < 0.53)
            return "circle";
        if (p < 0.72)
            return "brightness_7";
        if (p < 0.78)
            return "contrast";
        return "brightness_3";
    }

    Timer {
        interval: 3600000
        running: true
        repeat: true
        onTriggered: root.now = new Date()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.medium * root.widgetScale

        MaterialIcon {
            text: root.moonIcon()
            color: root.accentColour
            fontStyle: Tokens.font.icon.builders.extraLarge.scale(1.8 * root.widgetScale).build()
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            StyledText {
                Layout.fillWidth: true
                visible: root.opts.showName !== false
                text: root.phaseName()
                font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.opts.showIllumination !== false
                text: root.tr("Illumination", "Iluminación", "Beleuchtung") + ": " + Math.round(root.illumination * 100) + "%"
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                text: Qt.formatDate(root.now, "d MMMM")
                color: Colours.palette.m3outline
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.southern
        text: root.tr("Southern hemisphere", "Hemisferio sur", "Südhalbkugel")
        color: Colours.palette.m3outline
        font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
    }
}
