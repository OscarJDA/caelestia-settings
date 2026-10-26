pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.Services
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Audio visualiser", "Visualizador de audio", "Audio-Visualisierer")
    iconName: "graphic_eq"
    cardWidth: 320

    readonly property int barCount: Math.max(8, Math.min(128, Number(root.opts.bars) || 48))
    readonly property var values: Audio.cava.values
    readonly property bool idle: {
        const values = root.values ?? [];
        for (let i = 0; i < values.length; i++) {
            if (values[i] > 0.01)
                return false;
        }
        return true;
    }

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

    Item {
        Layout.fillWidth: true
        implicitHeight: 56 * root.widgetScale

        RowLayout {
            anchors.fill: parent
            spacing: 2 * root.widgetScale

            Repeater {
                model: root.barCount

                delegate: StyledRect {
                    required property int index

                    readonly property real value: Math.max(0, Math.min(1, root.valueAt(index)))

                    Layout.fillWidth: true
                    Layout.alignment: root.opts.mirror === true ? Qt.AlignVCenter : Qt.AlignBottom
                    Layout.preferredHeight: Math.max(2 * root.widgetScale, value * 56 * root.widgetScale)
                    radius: Tokens.rounding.extraSmall
                    color: Qt.alpha(root.accentColour, 0.35 + value * 0.65)
                }
            }
        }
    }
}
