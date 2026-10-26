pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.Images
import Caelestia.Services
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Audio visualiser", "Visualizador de audio", "Audio-Visualisierer")
    iconName: "graphic_eq"

    readonly property int barCount: Math.max(8, Math.min(128, Number(root.opts.bars) || 48))
    readonly property real widthScale: Math.max(0.5, Math.min(4, Number(root.opts.widthScale) || 1))
    readonly property real heightScale: Math.max(0.5, Math.min(4, Number(root.opts.heightScale) || 1))
    readonly property string styleName: root.opts.style ?? "bars"
    readonly property string colorMode: root.opts.colorMode ?? "artwork"

    cardWidth: 320 * root.widthScale

    readonly property var player: Players.active
    readonly property string artUrl: root.player ? Players.getArtUrl(root.player) : ""
    readonly property var values: Audio.cava.values
    readonly property bool idle: {
        const values = root.values ?? [];
        for (let i = 0; i < values.length; i++) {
            if (values[i] > 0.01)
                return false;
        }
        return true;
    }

    // The analyser returns the most common colour in the cover.  Dark or
    // desaturated covers fall back to the card accent so the bars stay visible.
    ImageAnalyser {
        id: analyser

        sourceItem: artProbe
        rescaleSize: 64
    }

    function vibrantColour(colour: color): color {
        if (!colour || colour.hslSaturation < 0.08 || colour.hslLightness < 0.03)
            return root.accentColour;
        const hue = colour.hslHue >= 0 ? colour.hslHue : root.accentColour.hslHue;
        const saturation = Math.max(0.55, Math.min(1, colour.hslSaturation));
        const lightness = Math.max(0.55, Math.min(0.8, colour.hslLightness));
        return Qt.hsla(hue, saturation, lightness, 1);
    }

    readonly property color visualiserColour: root.colorMode === "artwork" && root.artUrl !== "" ? root.vibrantColour(analyser.dominantColour) : root.accentColour

    visible: root.opts.showWhenIdle === true || !root.idle

    // Keep Cava alive while this widget exists instead of relying on the bar's
    // dashboard/media visualiser to reference the service.
    ServiceRef {
        service: Audio.cava
    }

    // Audio.cava.bars is shared with the background and dashboard visualisers,
    // so resample the values to the widget's own bar count instead of
    // overwriting the service setting.
    function valueAt(index: int): real {
        const count = root.values?.length ?? 0;
        if (count <= 0)
            return 0;
        if (count === root.barCount)
            return root.values[index] ?? 0;

        const position = index * (count - 1) / Math.max(1, root.barCount - 1);
        const low = Math.floor(position);
        const high = Math.min(count - 1, low + 1);
        const fraction = position - low;
        const a = root.values[low] ?? 0;
        const b = root.values[high] ?? 0;
        return a + (b - a) * fraction;
    }

    function paintBars(ctx: var, count: int, w: real, h: real): void {
        const gap = Math.max(1, 2 * root.widgetScale);
        const barWidth = Math.max(1, (w - gap * (count - 1)) / count);
        const amplitude = Math.max(1, h - 4);

        for (let i = 0; i < count; i++) {
            const value = Math.max(0, Math.min(1, root.valueAt(i)));
            const barHeight = Math.max(1.5 * root.widgetScale, value * amplitude);
            const x = i * (barWidth + gap);
            const y = root.opts.mirror === true ? (h - barHeight) / 2 : h - barHeight;
            ctx.fillStyle = Qt.alpha(root.visualiserColour, 0.35 + value * 0.65);
            ctx.fillRect(x, y, barWidth, barHeight);
        }
    }

    function traceCurve(ctx: var, points: var): void {
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length - 1; i++) {
            const xc = (points[i].x + points[i + 1].x) / 2;
            const yc = (points[i].y + points[i + 1].y) / 2;
            ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
        }
        const last = points[points.length - 1];
        ctx.quadraticCurveTo(last.x, last.y, last.x, last.y);
    }

    function paintCurve(ctx: var, count: int, w: real, h: real): void {
        const centre = h / 2;
        const amplitude = Math.max(1, (root.opts.mirror === true ? centre : h) - 4);
        const points = [];
        for (let i = 0; i < count; i++) {
            const value = Math.max(0, Math.min(1, root.valueAt(i)));
            const x = i * w / Math.max(1, count - 1);
            const y = (root.opts.mirror === true ? centre : h) - value * amplitude;
            points.push({ x: x, y: y });
        }

        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.lineWidth = Math.max(1.5, 2 * root.widgetScale);

        if (root.opts.mirror === true) {
            const lower = points.map(point => ({ x: point.x, y: h - point.y }));

            ctx.beginPath();
            root.traceCurve(ctx, points);
            for (let i = lower.length - 1; i >= 0; i--)
                ctx.lineTo(lower[i].x, lower[i].y);
            ctx.closePath();
            ctx.fillStyle = Qt.alpha(root.visualiserColour, 0.18);
            ctx.fill();

            ctx.beginPath();
            root.traceCurve(ctx, points);
            ctx.strokeStyle = root.visualiserColour;
            ctx.stroke();

            ctx.beginPath();
            root.traceCurve(ctx, lower);
            ctx.strokeStyle = Qt.alpha(root.visualiserColour, 0.65);
            ctx.stroke();
            return;
        }

        ctx.beginPath();
        root.traceCurve(ctx, points);
        ctx.lineTo(w, h);
        ctx.lineTo(0, h);
        ctx.closePath();
        ctx.fillStyle = Qt.alpha(root.visualiserColour, 0.18);
        ctx.fill();

        ctx.beginPath();
        root.traceCurve(ctx, points);
        ctx.strokeStyle = root.visualiserColour;
        ctx.stroke();
    }

    function paintPulse(ctx: var, count: int, w: real, h: real): void {
        const step = count > 1 ? w / (count - 1) : 0;
        const maxRadius = Math.max(2, Math.min(h / 2 - 4, w / count * 0.45));

        for (let i = 0; i < count; i++) {
            const value = Math.max(0, Math.min(1, root.valueAt(i)));
            const radius = Math.max(1.5, 1.5 + value * maxRadius);
            const x = count > 1 ? i * step : w / 2;
            const y = h / 2;

            ctx.beginPath();
            ctx.arc(x, y, radius * 2.1, 0, Math.PI * 2);
            ctx.fillStyle = Qt.alpha(root.visualiserColour, 0.08 + value * 0.1);
            ctx.fill();

            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fillStyle = Qt.alpha(root.visualiserColour, 0.35 + value * 0.65);
            ctx.fill();
        }
    }

    Item {
        Layout.fillWidth: true
        implicitHeight: Math.round(56 * root.widgetScale * root.heightScale)

        // Invisible probe used by ImageAnalyser.  Using an Image item instead
        // of a path also works for players that expose http(s) artwork.
        Item {
            id: artProbe

            width: 64
            height: 64
            opacity: 0.01
            visible: root.visible
            z: -1

            Image {
                id: artImage

                anchors.fill: parent
                source: root.artUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true

                onStatusChanged: {
                    if (status === Image.Ready)
                        analyser.requestUpdate();
                }
            }
        }

        Canvas {
            id: visual

            anchors.fill: parent

            onPaint: {
                const ctx = getContext("2d");
                ctx.reset();
                ctx.clearRect(0, 0, width, height);

                const count = root.barCount;
                if (count <= 0 || width <= 0 || height <= 0)
                    return;

                if (root.styleName === "curve")
                    root.paintCurve(ctx, count, width, height);
                else if (root.styleName === "pulse")
                    root.paintPulse(ctx, count, width, height);
                else
                    root.paintBars(ctx, count, width, height);
            }
        }
    }

    onValuesChanged: visual.requestPaint()
    onStyleNameChanged: visual.requestPaint()
    onColorModeChanged: visual.requestPaint()
    onVisualiserColourChanged: visual.requestPaint()
    onBarCountChanged: visual.requestPaint()
    onWidthChanged: visual.requestPaint()
    onHeightChanged: visual.requestPaint()
    onVisibleChanged: {
        if (visible) {
            visual.requestPaint();
            analyser.requestUpdate();
        }
    }

    onOptsChanged: visual.requestPaint()
}
