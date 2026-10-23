pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Stopwatch", "Cronómetro", "Stoppuhr")
    iconName: "av_timer"
    cardWidth: 260

    property bool running: false
    property double elapsed: 0
    property double startedAt: 0
    property double nowMs: Date.now()
    property var laps: []

    function reset(): void {
        root.running = false;
        root.elapsed = 0;
        root.startedAt = 0;
        root.nowMs = Date.now();
        root.laps = [];
    }

    function toggle(): void {
        if (root.running) {
            root.elapsed = root.currentMillis();
            root.running = false;
        } else {
            root.nowMs = Date.now();
            root.startedAt = root.nowMs;
            root.running = true;
        }
    }

    function addLap(): void {
        if (!root.running && root.elapsed === 0)
            return;
        const total = root.currentMillis();
        const previous = root.laps.length > 0 ? root.laps[0].total : 0;
        root.laps = [{ total: total, split: total - previous }].concat(root.laps).slice(0, 4);
    }

    function currentMillis(): double {
        return root.elapsed + (root.running ? root.nowMs - root.startedAt : 0);
    }

    function format(value: double, hundredths: bool): string {
        const totalSeconds = Math.floor(value / 1000);
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;
        let text = "";
        if (hours > 0)
            text += hours.toString().padStart(2, "0") + ":";
        text += minutes.toString().padStart(2, "0") + ":" + seconds.toString().padStart(2, "0");
        if (hundredths)
            text += "." + Math.floor((value % 1000) / 10).toString().padStart(2, "0");
        return text;
    }

    Timer {
        interval: 40
        repeat: true
        running: root.running
        onTriggered: root.nowMs = Date.now()
    }

    StyledText {
        Layout.fillWidth: true
        text: root.format(root.currentMillis(), root.opts.showHundredths !== false)
        color: root.running ? root.accentColour : Colours.palette.m3onSurface
        horizontalAlignment: Text.AlignHCenter
        font: Tokens.font.headline.builders.medium.scale(1.5 * root.widgetScale).build()
    }

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: Tokens.spacing.small * root.widgetScale

        WidgetIconButton {
            icon: root.running ? "pause" : "play_arrow"
            widgetScale: root.widgetScale
            onClicked: root.toggle()
        }

        WidgetIconButton {
            icon: "flag"
            widgetScale: root.widgetScale
            enabled: root.running || root.elapsed > 0
            onClicked: root.addLap()
        }

        WidgetIconButton {
            icon: "restart_alt"
            widgetScale: root.widgetScale
            enabled: root.running || root.elapsed > 0
            onClicked: root.reset()
        }
    }

    Repeater {
        model: root.laps

        delegate: RowLayout {
            required property var modelData
            required property int index

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale

            StyledText {
                text: "#" + (root.laps.length - index)
                color: Colours.palette.m3outline
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                text: "+" + root.format(modelData.split, true)
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                text: root.format(modelData.total, true)
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            }
        }
    }
}
