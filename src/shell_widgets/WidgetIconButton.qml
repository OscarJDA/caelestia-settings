pragma ComponentBehavior: Bound

import QtQuick
import Caelestia.Config
import qs.components.controls

IconButton {
    id: root

    property real widgetScale: 1

    type: IconButton.Text
    font: Tokens.font.icon.builders.small.scale(root.widgetScale).build()
    padding: Tokens.padding.extraSmall * root.widgetScale
}
