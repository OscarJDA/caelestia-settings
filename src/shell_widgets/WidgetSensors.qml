pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Sensors", "Sensores", "Sensoren")
    iconName: "device_thermostat"
    cardWidth: 300

    readonly property int maxItems: Math.max(1, Math.min(20, Number(root.opts.maxItems) || 4))
    readonly property bool wantTemps: root.opts.showTemps !== false
    readonly property bool wantFans: root.opts.showFans !== false

    property var items: []

    function prettyAdapter(name: string): string {
        return name.replace(/-(isa|pci|virtual|acpi)-\d+$/, "").replace(/_/g, " ").replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }

    function parse(text: string): var {
        let json;
        try {
            json = JSON.parse(text);
        } catch (error) {
            return [];
        }

        const result = [];
        for (const adapter in json) {
            const group = json[adapter];
            if (!group || typeof group !== "object")
                continue;
            for (const chip in group) {
                const values = group[chip];
                if (!values || typeof values !== "object")
                    continue;
                for (const key in values) {
                    if (!key.endsWith("_input"))
                        continue;
                    const base = key.slice(0, -6);
                    const value = Number(values[key]);
                    if (!Number.isFinite(value))
                        continue;

                    const isFan = base.startsWith("fan");
                    const isTemp = base.startsWith("temp");
                    if (isFan && !root.wantFans)
                        continue;
                    if (isTemp && !root.wantTemps)
                        continue;
                    if (!isFan && !isTemp)
                        continue;

                    const label = root.prettyAdapter(adapter) + " · " + base.replace(/^temp|^fan/, match => match === "temp" ? root.tr("Temp ", "Temp ", "Temp ") : root.tr("Fan ", "Vent. ", "Lüfter "));
                    result.push({
                        key: `${adapter}/${base}`,
                        label: label,
                        value: isFan ? Math.round(value) + " RPM" : value.toFixed(1) + " °C",
                        order: (isFan ? 1 : 0) * 1000 + (result.length)
                    });
                }
            }
        }

        result.sort((a, b) => a.order - b.order);
        return result.slice(0, root.maxItems);
    }

    Process {
        id: sensorsProcess

        command: ["sensors", "-j"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: root.items = root.parse(text)
        }
    }

    Timer {
        interval: 10000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: sensorsProcess.running = true
    }

    Repeater {
        model: root.items

        delegate: WidgetStat {
            required property var modelData

            iconName: modelData.key.indexOf("fan") >= 0 ? "mode_fan" : "thermostat"
            label: modelData.label
            valueText: modelData.value
            showBar: false
            widgetScale: root.widgetScale
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.items.length === 0
        text: root.tr("No sensors reported by lm_sensors", "lm_sensors no reporta sensores", "lm_sensors meldet keine Sensoren")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
        wrapMode: Text.WordWrap
    }
}
