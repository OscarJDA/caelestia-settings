pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

WidgetCard {
    id: root

    title: tr("Pomodoro", "Pomodoro", "Pomodoro")
    iconName: "timer"
    cardWidth: 260

    readonly property int workMinutes: Math.max(1, Number(root.opts.workMinutes) || 25)
    readonly property int shortMinutes: Math.max(1, Number(root.opts.shortBreakMinutes) || 5)
    readonly property int longMinutes: Math.max(1, Number(root.opts.longBreakMinutes) || 15)
    readonly property int longEvery: Math.max(1, Number(root.opts.longBreakEvery) || 4)

    property string phase: "work"
    property int remaining: root.workMinutes * 60
    property bool running: false
    property int completed: 0
    property int sessionLength: root.workMinutes * 60

    readonly property real progress: root.sessionLength > 0 ? 1 - root.remaining / root.sessionLength : 0
    readonly property bool isBreak: root.phase !== "work"
    readonly property color phaseColour: root.isBreak ? Colours.palette.m3tertiary : root.accentColour

    function durationFor(phase: string): int {
        switch (phase) {
        case "short":
            return root.shortMinutes * 60;
        case "long":
            return root.longMinutes * 60;
        default:
            return root.workMinutes * 60;
        }
    }

    function phaseLabel(): string {
        switch (root.phase) {
        case "short":
            return root.tr("Short break", "Descanso corto", "Kurze Pause");
        case "long":
            return root.tr("Long break", "Descanso largo", "Lange Pause");
        default:
            return root.tr("Focus", "Concentración", "Fokus");
        }
    }

    function clockText(): string {
        const minutes = Math.floor(root.remaining / 60);
        const seconds = root.remaining % 60;
        return minutes.toString().padStart(2, "0") + ":" + seconds.toString().padStart(2, "0");
    }

    function setPhase(phase: string, autoStart: bool): void {
        root.phase = phase;
        root.sessionLength = root.durationFor(phase);
        root.remaining = root.sessionLength;
        root.running = autoStart;
    }

    function skip(): void {
        const next = root.phase === "work" ? (root.completed % root.longEvery === 0 ? "long" : "short") : "work";
        root.setPhase(next, false);
    }

    function reset(): void {
        root.running = false;
        root.setPhase(root.phase, false);
    }

    function finish(): void {
        if (root.phase === "work") {
            root.completed += 1;
            const longBreak = root.completed % root.longEvery === 0;
            root.setPhase(longBreak ? "long" : "short", root.opts.autoStartBreaks === true);
        } else {
            root.setPhase("work", false);
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.running
        onTriggered: {
            if (root.remaining > 0)
                root.remaining -= 1;
            if (root.remaining <= 0) {
                root.running = false;
                root.finish();
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.medium * root.widgetScale

        Item {
            implicitWidth: 78 * root.widgetScale
            implicitHeight: 78 * root.widgetScale

            CircularProgress {
                anchors.fill: parent
                value: root.progress
                strokeWidth: Tokens.padding.small * root.widgetScale
                fgColour: root.phaseColour
            }

            StyledText {
                anchors.centerIn: parent
                text: root.clockText()
                color: root.phaseColour
                font: Tokens.font.title.builders.medium.scale(root.widgetScale).build()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            StyledText {
                Layout.fillWidth: true
                text: root.phaseLabel()
                font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                text: root.tr("%1 done today", "%1 hoy", "%1 heute").arg(root.completed)
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            RowLayout {
                spacing: Tokens.spacing.small * root.widgetScale

                WidgetIconButton {
                    icon: root.running ? "pause" : "play_arrow"
                    widgetScale: root.widgetScale
                    onClicked: root.running = !root.running
                }

                WidgetIconButton {
                    icon: "skip_next"
                    widgetScale: root.widgetScale
                    onClicked: root.skip()
                }

                WidgetIconButton {
                    icon: "restart_alt"
                    widgetScale: root.widgetScale
                    onClicked: root.reset()
                }
            }
        }
    }
}
