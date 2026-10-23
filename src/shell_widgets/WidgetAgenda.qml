pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Caelestia.Config
import Caelestia.I18n
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Agenda", "Agenda", "Agenda")
    iconName: "event_note"
    cardWidth: 320

    readonly property int maxEvents: Math.max(1, Math.min(12, Number(root.opts.maxEvents) || 5))
    readonly property int daysAhead: Math.max(1, Math.min(365, Number(root.opts.daysAhead) || 14))
    readonly property string filePath: root.expand(root.opts.path ?? "~/.config/caelestia-settings/agenda.ics")

    property var events: []

    function expand(path: string): string {
        if (path.startsWith("~/"))
            return (Quickshell.env("HOME") ?? "") + path.slice(1);
        return path;
    }

    function pad(value: int): string {
        return value.toString().padStart(2, "0");
    }

    function parseDate(value: string): date {
        const digits = value.replace(/[^0-9]/g, "");
        if (digits.length < 8)
            return new Date(NaN);
        const year = Number(digits.slice(0, 4));
        const month = Number(digits.slice(4, 6)) - 1;
        const day = Number(digits.slice(6, 8));
        if (digits.length >= 14)
            return new Date(year, month, day, Number(digits.slice(9, 11)), Number(digits.slice(11, 13)));
        return new Date(year, month, day);
    }

    function decode(value: string): string {
        return value.replace(/\\n/gi, " ").replace(/\\,/g, ",").replace(/\\;/g, ";");
    }

    function parse(text: string): var {
        const unfolded = text.replace(/\r?\n[ \t]/g, "");
        const lines = unfolded.split(/\r?\n/);
        const result = [];
        const now = new Date();
        const limit = new Date(now.getTime() + root.daysAhead * 86400000);
        let current = null;

        for (const line of lines) {
            if (line === "BEGIN:VEVENT") {
                current = {};
                continue;
            }
            if (line === "END:VEVENT") {
                if (current && current.summary) {
                    const when = current.start ?? new Date(NaN);
                    if (!isNaN(when.getTime()) && when >= new Date(now.getFullYear(), now.getMonth(), now.getDate()) && when <= limit)
                        result.push(current);
                }
                current = null;
                continue;
            }
            if (!current)
                continue;

            const split = line.indexOf(":");
            if (split < 0)
                continue;
            const key = line.slice(0, split).split(";")[0].toUpperCase();
            const value = line.slice(split + 1);

            if (key === "SUMMARY")
                current.summary = root.decode(value);
            else if (key === "LOCATION")
                current.location = root.decode(value);
            else if (key === "DTSTART")
                current.start = root.parseDate(value);
        }

        result.sort((a, b) => a.start - b.start);
        return result.slice(0, root.maxEvents);
    }

    function dayLabel(value: date): string {
        const today = new Date();
        const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        const target = new Date(value.getFullYear(), value.getMonth(), value.getDate());
        const diff = Math.round((target - start) / 86400000);
        if (diff === 0)
            return root.tr("Today", "Hoy", "Heute");
        if (diff === 1)
            return root.tr("Tomorrow", "Mañana", "Morgen");
        return Qt.formatDate(value, "ddd d MMM");
    }

    function timeLabel(value: date): string {
        if (value.getHours() === 0 && value.getMinutes() === 0)
            return "";
        return Qt.formatDateTime(value, Units.twelveHourClock ? "h:mm AP" : "HH:mm");
    }

    FileView {
        id: agendaFile

        path: root.filePath
        watchChanges: true
        printErrors: false

        onFileChanged: reload()
        onLoaded: root.events = root.parse(text())
        onLoadFailed: root.events = []
    }

    Repeater {
        model: root.events

        delegate: RowLayout {
            id: event

            required property var modelData

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale

            StyledRect {
                implicitWidth: 4 * root.widgetScale
                implicitHeight: column.implicitHeight
                radius: Tokens.rounding.full
                color: root.accentColour
            }

            ColumnLayout {
                id: column

                Layout.fillWidth: true
                spacing: 0

                StyledText {
                    Layout.fillWidth: true
                    text: event.modelData.summary
                    font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    text: root.dayLabel(event.modelData.start) + (root.timeLabel(event.modelData.start) !== "" ? " · " + root.timeLabel(event.modelData.start) : "")
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                    elide: Text.ElideRight
                }

                StyledText {
                    Layout.fillWidth: true
                    visible: root.opts.showLocation !== false && (event.modelData.location ?? "") !== ""
                    text: event.modelData.location ?? ""
                    color: Colours.palette.m3outline
                    font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                    elide: Text.ElideRight
                }
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.events.length === 0
        text: root.tr("No upcoming events", "Sin eventos próximos", "Keine anstehenden Termine")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
