pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.I18n
import Caelestia.Services
import qs.components
import qs.services
import qs.utils

WidgetCard {
    id: root

    title: tr("Storage", "Almacenamiento", "Speicher")
    iconName: "hard_drive"
    cardWidth: 300

    readonly property int maxDisks: Math.max(1, Math.min(8, Number(root.opts.maxDisks) || 4))

    ServiceRef {
        service: Storage
    }

    Repeater {
        model: Storage.disks

        delegate: WidgetStat {
            id: disk

            required property var modelData
            required property int index

            visible: index < root.maxDisks && modelData.total > 0
            iconName: modelData.hasRoot ? "hard_drive" : "folder"
            label: modelData.mount
            value: modelData.perc
            detail: {
                if (!root.opts.showFree)
                    return Units.formatKibUsage(modelData.used, modelData.total);
                return Units.formatKibUsage(modelData.used, modelData.total) + "  ·  " + Units.formatKibUsage(modelData.free, modelData.total) + " " + root.tr("free", "libre", "frei");
            }
            showBar: root.opts.showBars !== false
            widgetScale: root.widgetScale
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: Storage.disks.length === 0
        text: root.tr("No disks detected", "No se detectaron discos", "Keine Datenträger erkannt")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
