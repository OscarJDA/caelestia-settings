pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("Weather", "Clima", "Wetter")
    iconName: Weather.icon
    cardWidth: 300

    Component.onCompleted: Weather.reload()

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.medium * root.widgetScale

        MaterialIcon {
            text: Weather.icon
            color: root.accentColour
            fontStyle: Tokens.font.icon.builders.extraLarge.scale(1.5 * root.widgetScale).build()
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            StyledText {
                Layout.fillWidth: true
                text: Weather.cc ? Weather.temp : "--"
                color: root.accentColour
                font: Tokens.font.headline.builders.medium.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                text: Weather.cc ? Weather.description : tr("No weather", "Sin datos del clima", "Keine Wetterdaten")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }
        }

        StyledText {
            visible: root.opts.showCity !== false && Weather.city !== ""
            text: Weather.city ?? ""
            color: Colours.palette.m3outline
            font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            elide: Text.ElideRight
            Layout.maximumWidth: 110 * root.widgetScale
        }
    }

    WidgetStat {
        visible: root.opts.showFeelsLike !== false
        iconName: "thermostat"
        label: tr("Feels like", "Sensación", "Gefühlt")
        valueText: Weather.feelsLike
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showHumidity !== false
        iconName: "humidity_percentage"
        label: tr("Humidity", "Humedad", "Luftfeuchtigkeit")
        valueText: Weather.humidity + "%"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showWind !== false
        iconName: "air"
        label: tr("Wind", "Viento", "Wind")
        valueText: Math.round(Weather.windSpeed) + " km/h"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showSun !== false
        iconName: "wb_twilight"
        label: tr("Sunrise", "Amanecer", "Sonnenaufgang")
        valueText: Weather.sunrise
        showBar: false
        widgetScale: root.widgetScale
    }
}
