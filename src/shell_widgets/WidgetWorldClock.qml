pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.I18n
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("World clock", "Reloj mundial", "Weltuhr")
    iconName: "public"
    cardWidth: 280

    property date now: new Date()

    readonly property var cities: root.parseCities(root.opts.cities ?? "")

    function parseCities(raw: string): var {
        const result = [];
        for (const piece of raw.split(",")) {
            const text = piece.trim();
            if (text === "")
                continue;
            const split = text.lastIndexOf(":");
            if (split <= 0)
                continue;
            const name = text.slice(0, split).trim();
            const offset = Number(text.slice(split + 1));
            if (name === "" || !Number.isFinite(offset))
                continue;
            result.push({ name: name, offset: offset });
        }
        return result;
    }

    function cityTime(offset: real): string {
        const local = root.now;
        const utc = local.getTime() + local.getTimezoneOffset() * 60000;
        const city = new Date(utc + offset * 3600000);
        const twelve = root.opts.format === "12h" || (root.opts.format !== "24h" && Units.twelveHourClock);
        return Qt.formatDateTime(city, twelve ? "h:mm AP" : "HH:mm");
    }

    function offsetText(offset: real): string {
        if (root.opts.showOffset === false)
            return "";
        return "UTC" + (offset >= 0 ? "+" : "") + offset;
    }

    Timer {
        interval: 10000
        running: true
        repeat: true
        onTriggered: root.now = new Date()
    }

    Repeater {
        model: root.cities

        delegate: RowLayout {
            required property var modelData

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale

            StyledText {
                Layout.fillWidth: true
                text: modelData.name
                font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                visible: root.opts.showOffset !== false
                text: root.offsetText(modelData.offset)
                color: Colours.palette.m3outline
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                text: root.cityTime(modelData.offset)
                color: root.accentColour
                font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.cities.length === 0
        text: root.tr("Add cities in settings, e.g. Tokyo:+9, London:+0", "Añade ciudades en ajustes, p. ej. Tokyo:+9, London:+0", "Städte in den Einstellungen hinzufügen, z. B. Tokyo:+9, London:+0")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        wrapMode: Text.WordWrap
    }
}
