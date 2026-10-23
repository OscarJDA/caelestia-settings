pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Top processes", "Procesos", "Top-Prozesse")
    iconName: "list_alt"
    cardWidth: 320

    readonly property int count: Math.max(1, Math.min(20, Number(root.opts.count) || 5))
    readonly property bool byMemory: root.opts.sortBy === "memory"

    property var items: []

    function parse(text: string): var {
        const rows = [];
        for (const line of text.split(/\r?\n/)) {
            const trimmed = line.trim();
            if (trimmed === "")
                continue;
            const parts = trimmed.split(/\s+/);
            if (parts.length < 3)
                continue;
            const mem = Number(parts[parts.length - 1]);
            const cpu = Number(parts[parts.length - 2]);
            if (!Number.isFinite(cpu) || !Number.isFinite(mem))
                continue;
            const name = parts.slice(0, parts.length - 2).join(" ");
            rows.push({ name: name, cpu: cpu, mem: mem });
        }

        rows.sort((a, b) => root.byMemory ? b.mem - a.mem : b.cpu - a.cpu);
        return rows.slice(0, root.count);
    }

    function percent(value: real): string {
        return value.toFixed(1) + "%";
    }

    Process {
        id: psProcess

        command: ["ps", "-eo", "comm,pcpu,pmem", "--no-headers"]
        running: false

        stdout: StdioCollector {
            onStreamFinished: root.items = root.parse(text)
        }
    }

    Timer {
        interval: 3000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: psProcess.running = true
    }

    Repeater {
        model: root.items

        delegate: RowLayout {
            required property var modelData

            Layout.fillWidth: true
            spacing: Tokens.spacing.small * root.widgetScale

            MaterialIcon {
                text: "terminal"
                color: Colours.palette.m3outline
                fontStyle: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
            }

            StyledText {
                Layout.fillWidth: true
                text: modelData.name
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                text: root.percent(root.byMemory ? modelData.mem : modelData.cpu)
                color: root.accentColour
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
            }
        }
    }
}
