pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQml
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: ""
    showHeader: false
    cardWidth: root.opts.weekNumbers === true ? 336 : 306

    property date now: new Date()
    property int monthOffset: 0

    readonly property date shownDate: new Date(root.now.getFullYear(), root.now.getMonth() + root.monthOffset, 1)
    readonly property int shownYear: root.shownDate.getFullYear()
    readonly property int shownMonth: root.shownDate.getMonth()
    readonly property int todayDay: root.now.getDate()
    readonly property bool isCurrentMonth: root.monthOffset === 0
    readonly property int firstDay: root.opts.startOfWeek === "monday" ? 1 : root.opts.startOfWeek === "sunday" ? 7 : Qt.locale().firstDayOfWeek
    readonly property bool weekNumbers: root.opts.weekNumbers === true
    readonly property bool showWeekdays: root.opts.showWeekdays !== false
    readonly property int firstOffset: {
        const first = new Date(root.shownYear, root.shownMonth, 1);
        return (first.getDay() - (root.firstDay % 7) + 7) % 7;
    }
    readonly property var cells: root.buildCells(root.shownYear, root.shownMonth)
    readonly property var gridCells: root.buildGrid(root.cells)

    function buildCells(year: int, month: int): var {
        const days = new Date(year, month + 1, 0).getDate();
        const cells = [];
        for (let i = 0; i < root.firstOffset; i++)
            cells.push(0);
        for (let i = 1; i <= days; i++)
            cells.push(i);
        while (cells.length < 42)
            cells.push(0);
        return cells;
    }

    function buildGrid(cells: var): var {
        if (!root.weekNumbers)
            return cells.map(day => ({ day: day }));

        const rows = [];
        for (let row = 0; row < 6; row++) {
            const weekDate = new Date(root.shownYear, root.shownMonth, 1 - root.firstOffset + row * 7);
            rows.push({ week: root.isoWeek(weekDate) });
            for (let column = 0; column < 7; column++)
                rows.push({ day: cells[row * 7 + column] });
        }
        return rows;
    }

    function isoWeek(date: date): int {
        const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
        const dayNum = d.getUTCDay() || 7;
        d.setUTCDate(d.getUTCDate() + 4 - dayNum);
        const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
    }

    function moveMonth(delta: int): void {
        root.monthOffset += delta;
    }

    Timer {
        interval: 60000
        running: true
        repeat: true
        onTriggered: root.now = new Date()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        MaterialIcon {
            text: "calendar_month"
            color: root.accentColour
            fontStyle: Tokens.font.icon.builders.medium.scale(root.widgetScale).build()
        }

        StyledText {
            Layout.fillWidth: true
            text: Qt.locale().monthName(root.shownMonth, Locale.LongFormat) + " " + root.shownYear
            font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
            elide: Text.ElideRight
        }

        WidgetIconButton {
            icon: "today"
            widgetScale: root.widgetScale
            visible: !root.isCurrentMonth
            onClicked: root.monthOffset = 0
        }

        WidgetIconButton {
            icon: "chevron_left"
            widgetScale: root.widgetScale
            onClicked: root.moveMonth(-1)
        }

        WidgetIconButton {
            icon: "chevron_right"
            widgetScale: root.widgetScale
            onClicked: root.moveMonth(1)
        }
    }

    GridLayout {
        Layout.fillWidth: true
        columns: root.weekNumbers ? 8 : 7
        rowSpacing: 0
        columnSpacing: 0

        Repeater {
            model: root.weekNumbers ? ["W"].concat(root.weekdayNames()) : root.weekdayNames()

            delegate: Item {
                required property var modelData

                Layout.fillWidth: true
                visible: root.showWeekdays
                implicitHeight: root.showWeekdays ? 20 * root.widgetScale : 0

                StyledText {
                    anchors.centerIn: parent
                    text: parent.modelData
                    color: Colours.palette.m3outline
                    font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                }
            }
        }

        Repeater {
            model: root.gridCells

            delegate: Item {
                id: cell

                required property var modelData

                readonly property bool isWeek: modelData.week !== undefined
                readonly property int day: modelData.day ?? 0
                readonly property bool today: !cell.isWeek && root.isCurrentMonth && cell.day === root.todayDay

                Layout.fillWidth: true
                implicitHeight: 28 * root.widgetScale

                StyledRect {
                    anchors.centerIn: parent
                    visible: cell.isWeek || cell.today
                    implicitWidth: 24 * root.widgetScale
                    implicitHeight: 24 * root.widgetScale
                    radius: Tokens.rounding.full
                    color: cell.isWeek ? "transparent" : Qt.alpha(root.accentColour, 0.18)
                }

                StyledText {
                    anchors.centerIn: parent
                    text: cell.isWeek ? cell.modelData.week : (cell.day === 0 ? "" : cell.day)
                    color: cell.isWeek ? Colours.palette.m3outline : (cell.today ? root.accentColour : Colours.palette.m3onSurface)
                    font: cell.isWeek ? Tokens.font.label.builders.small.scale(root.widgetScale).build() : (cell.today ? Tokens.font.label.builders.medium.scale(root.widgetScale).build() : Tokens.font.label.builders.small.scale(root.widgetScale).build())
                }
            }
        }
    }

    function weekdayNames(): var {
        const names = [];
        for (let i = 0; i < 7; i++) {
            const day = ((root.firstDay - 1 + i) % 7) + 1;
            names.push(Qt.locale().dayName(day, Locale.ShortFormat));
        }
        return names;
    }
}
