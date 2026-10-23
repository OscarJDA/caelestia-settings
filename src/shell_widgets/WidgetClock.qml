pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.I18n
import qs.components
import qs.services

WidgetCard {
    id: root

    title: ""
    showHeader: false
    cardWidth: 300

    readonly property bool showSeconds: opts.showSeconds === true
    readonly property string dateFormat: opts.dateFormat ?? "long"

    function timeText(): string {
        const twelve = opts.format === "12h" || (opts.format !== "24h" && Units.twelveHourClock);
        if (twelve)
            return Time.format(root.showSeconds ? "h:mm:ss AP" : "h:mm AP");
        return Time.format(root.showSeconds ? "HH:mm:ss" : "HH:mm");
    }

    function dateText(): string {
        const withWeekday = root.opts.showWeekday !== false;
        if (root.dateFormat === "iso")
            return Qt.formatDate(Time.date, "yyyy-MM-dd");
        if (root.dateFormat === "short")
            return Qt.formatDate(Time.date, withWeekday ? "ddd d MMM" : "d MMM");
        return Qt.formatDate(Time.date, withWeekday ? "dddd, d MMMM" : "d MMMM");
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.extraSmall

        StyledText {
            Layout.fillWidth: true
            text: root.timeText()
            color: root.accentColour
            horizontalAlignment: Text.AlignHCenter
            font: Tokens.font.headline.builders.large.scale(2.3 * root.widgetScale).width(30).build()
        }

        StyledText {
            Layout.fillWidth: true
            visible: root.opts.showWeekday !== false || root.opts.showDate !== false
            text: root.opts.showDate === false ? Qt.formatDate(Time.date, "dddd") : root.dateText()
            color: Colours.palette.m3onSurfaceVariant
            horizontalAlignment: Text.AlignHCenter
            font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
            elide: Text.ElideRight
        }
    }
}
