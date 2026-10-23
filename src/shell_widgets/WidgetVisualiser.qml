pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
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

    Component.onCompleted: root.applyBars()
    onBarCountChanged: root.applyBars()

    function applyBars(): void {
        Audio.cava.bars = root.barCount;
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

                    readonly property real value: Math.max(0, Math.min(1, root.values[index] ?? 0))

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
