pragma ComponentBehavior: Bound

import QtQuick
import Caelestia.Config
import qs.components

// Lightweight sparkline fed by Quickshell CircularBuffer instances.
Canvas {
    id: root

    property var buffer
    property var buffer2
    property color lineColour: Colours.palette.m3tertiary
    property color lineColour2: Colours.palette.m3secondary
    property real widgetScale: 1

    implicitWidth: 220
    implicitHeight: 44 * root.widgetScale
    opacity: root.visible ? 1 : 0

    function valuesOf(source: var): var {
        if (!source)
            return [];
        const result = [];
        const count = source.count ?? 0;
        for (let i = 0; i < count; i++)
            result.push(source.at(i));
        return result;
    }

    Connections {
        target: root.buffer

        function onValuesChanged(): void {
            root.requestPaint();
        }
    }

    Connections {
        target: root.buffer2

        function onValuesChanged(): void {
            root.requestPaint();
        }
    }

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        ctx.clearRect(0, 0, width, height);

        const first = root.valuesOf(root.buffer);
        const second = root.valuesOf(root.buffer2);
        if (first.length < 2 && second.length < 2)
            return;

        const maxValue = Math.max(root.buffer?.maximum ?? 0, root.buffer2?.maximum ?? 0, 1);
        const pointCount = Math.max(first.length, second.length);
        const step = width / Math.max(1, pointCount - 1);

        const drawLine = (values, colour) => {
            if (!values || values.length < 2)
                return;
            ctx.beginPath();
            for (let i = 0; i < values.length; i++) {
                const x = i * step;
                const y = height - Math.max(0, Math.min(1, values[i] / maxValue)) * (height - 2) - 1;
                if (i === 0)
                    ctx.moveTo(x, y);
                else
                    ctx.lineTo(x, y);
            }
            ctx.strokeStyle = colour;
            ctx.lineWidth = Math.max(1, 1.5 * root.widgetScale);
            ctx.lineJoin = "round";
            ctx.lineCap = "round";
            ctx.stroke();
        };

        drawLine(first, root.lineColour);
        drawLine(second, root.lineColour2);
    }
}
