pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Forecast", "Pronóstico", "Vorhersage")
    iconName: "thermostat"
    cardWidth: 344

    readonly property int count: Math.max(1, Math.min(12, Number(root.opts.count) || 6))
    readonly property bool showHourly: root.opts.mode !== "daily"
    readonly property bool showDaily: root.opts.mode !== "hourly"
    readonly property var hourly: (Weather.hourlyForecast ?? []).slice(0, root.count)
    readonly property var daily: (Weather.forecast ?? []).slice(0, root.count)

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.extraSmall
        visible: root.showHourly && root.hourly.length > 0

        StyledText {
            text: root.tr("Next hours", "Próximas horas", "Nächste Stunden")
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Tokens.spacing.extraSmall

            Repeater {
                model: root.hourly

                delegate: ColumnLayout {
                    required property var modelData

                    Layout.fillWidth: true
                    spacing: 2 * root.widgetScale

                    StyledText {
                        Layout.fillWidth: true
                        text: modelData.hour.toString().padStart(2, "0") + ":00"
                        color: Colours.palette.m3onSurfaceVariant
                        horizontalAlignment: Text.AlignHCenter
                        font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                    }

                    MaterialIcon {
                        Layout.alignment: Qt.AlignHCenter
                        text: modelData.icon
                        color: root.accentColour
                        fontStyle: Tokens.font.icon.builders.medium.scale(root.widgetScale).build()
                    }

                    StyledText {
                        Layout.fillWidth: true
                        text: Weather.formatTemp(modelData.tempC, true)
                        horizontalAlignment: Text.AlignHCenter
                        font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
                    }

                    StyledText {
                        Layout.fillWidth: true
                        visible: root.opts.showPrecip !== false && modelData.precipChance > 0
                        text: modelData.precipChance + "%"
                        color: Colours.palette.m3tertiary
                        horizontalAlignment: Text.AlignHCenter
                        font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                    }
                }
            }
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.extraSmall
        visible: root.showDaily && root.daily.length > 0

        StyledText {
            text: root.tr("Next days", "Próximos días", "Nächste Tage")
            color: Colours.palette.m3onSurfaceVariant
            font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
        }

        Repeater {
            model: root.daily

            delegate: RowLayout {
                required property var modelData

                Layout.fillWidth: true
                spacing: Tokens.spacing.small * root.widgetScale

                StyledText {
                    Layout.fillWidth: true
                    text: Qt.formatDate(new Date(modelData.date), "ddd d")
                    font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
                }

                MaterialIcon {
                    text: modelData.icon
                    color: root.accentColour
                    fontStyle: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
                }

                StyledText {
                    text: Weather.formatTemp(modelData.maxTempC, true)
                    font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
                }

                StyledText {
                    text: Weather.formatTemp(modelData.minTempC, true)
                    color: Colours.palette.m3onSurfaceVariant
                    font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
                }
            }
        }
    }
}
