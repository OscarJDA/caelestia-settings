pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

WidgetCard {
    id: root

    title: tr("Air quality", "Calidad del aire", "Luftqualität")
    iconName: "air"
    cardWidth: 300

    property var data: null
    property bool failed: false

    readonly property bool useUs: root.opts.pollutant === "us"
    readonly property var current: root.data?.current ?? null
    readonly property real aqi: root.useUs ? (root.current?.us_aqi ?? -1) : (root.current?.european_aqi ?? -1)
    readonly property int maxScale: root.useUs ? 300 : 100
    readonly property color aqiColour: root.colourFor(root.aqi)

    function colourFor(value: real): color {
        if (value < 0)
            return Colours.palette.m3outline;
        if (value <= root.maxScale * 0.25)
            return Colours.palette.m3tertiary;
        if (value <= root.maxScale * 0.5)
            return Colours.palette.m3primary;
        if (value <= root.maxScale * 0.75)
            return Colours.palette.m3secondary;
        return Colours.palette.m3error;
    }

    function qualityLabel(): string {
        if (root.aqi < 0)
            return root.tr("No data", "Sin datos", "Keine Daten");
        if (root.aqi <= root.maxScale * 0.25)
            return root.tr("Good", "Buena", "Gut");
        if (root.aqi <= root.maxScale * 0.5)
            return root.tr("Moderate", "Moderada", "Mäßig");
        if (root.aqi <= root.maxScale * 0.75)
            return root.tr("Poor", "Mala", "Schlecht");
        return root.tr("Very poor", "Muy mala", "Sehr schlecht");
    }

    function fetch(): void {
        const loc = Weather.loc ?? "";
        if (loc.indexOf(",") === -1)
            return;
        const [lat, lon] = loc.split(",").map(part => part.trim());
        Requests.get(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lat}&longitude=${lon}&current=european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,sulphur_dioxide`, text => {
            try {
                root.data = JSON.parse(text);
                root.failed = false;
            } catch (error) {
                root.failed = true;
            }
        }, () => {
            root.failed = true;
        });
    }

    Timer {
        interval: 900000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.fetch()
    }

    WidgetStat {
        visible: root.aqi >= 0
        iconName: "eco"
        label: root.qualityLabel()
        valueText: Math.round(root.aqi) + (root.useUs ? " US AQI" : " EAQI")
        showBar: true
        accent: root.aqiColour
        widgetScale: root.widgetScale
    }

    StyledProgressBar {
        Layout.fillWidth: true
        visible: root.aqi >= 0
        value: Math.max(0, Math.min(1, root.aqi / root.maxScale))
        implicitHeight: Tokens.padding.extraSmall * 2 * root.widgetScale
        fgColour: root.aqiColour
    }

    WidgetStat {
        visible: root.opts.showPm !== false && root.current !== null
        iconName: "blur_on"
        label: root.tr("PM2.5", "PM2.5", "PM2.5")
        valueText: Math.round(root.current?.pm2_5 ?? 0) + " µg/m³"
        showBar: false
        widgetScale: root.widgetScale
    }

    WidgetStat {
        visible: root.opts.showPm !== false && root.current !== null
        iconName: "blur_circular"
        label: root.tr("PM10", "PM10", "PM10")
        valueText: Math.round(root.current?.pm10 ?? 0) + " µg/m³"
        showBar: false
        widgetScale: root.widgetScale
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.aqi < 0
        text: root.failed ? root.tr("Could not load air quality", "No se pudo cargar la calidad del aire", "Luftqualität konnte nicht geladen werden") : root.tr("Waiting for location…", "Esperando ubicación…", "Warte auf Standort…")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        wrapMode: Text.WordWrap
    }
}
