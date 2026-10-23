pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import qs.components
import qs.components.controls
import qs.services

WidgetCard {
    id: root

    title: tr("Media", "Multimedia", "Medien")
    iconName: "music_note"
    cardWidth: 340
    visible: !(root.opts.hideWhenStopped === true && !root.playing)

    readonly property var player: Players.active
    readonly property bool playing: root.player?.isPlaying ?? false
    readonly property string artUrl: root.player ? Players.getArtUrl(root.player) : ""
    readonly property real length: root.player?.length ?? 0

    property real position: 0

    readonly property real progress: root.length > 0 ? Math.max(0, Math.min(1, root.position / root.length)) : 0

    function syncPosition(): void {
        root.position = root.player?.position ?? 0;
    }

    Component.onCompleted: root.syncPosition()

    Connections {
        target: Players

        function onActiveChanged(): void {
            root.syncPosition();
        }
    }

    Connections {
        target: root.player

        function onPositionChanged(): void {
            root.syncPosition();
        }

        function onLengthChanged(): void {
            root.syncPosition();
        }
    }

    // MPRIS only emits positionChanged on D-Bus updates and seeks, so sample
    // the position to keep the progress bar moving during playback.
    Timer {
        interval: root.playing ? 500 : 1000
        running: root.player !== null
        repeat: true
        triggeredOnStart: true
        onTriggered: root.syncPosition()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.medium * root.widgetScale

        StyledClippingRect {
            visible: root.opts.showArt !== false
            implicitWidth: 64 * root.widgetScale
            implicitHeight: 64 * root.widgetScale
            radius: Tokens.rounding.medium * root.widgetScale
            color: Colours.palette.m3surfaceContainerHigh

            Image {
                anchors.fill: parent
                source: root.artUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: root.artUrl !== ""
            }

            MaterialIcon {
                anchors.centerIn: parent
                visible: root.artUrl === ""
                text: "music_note"
                color: Colours.palette.m3onSurfaceVariant
                fontStyle: Tokens.font.icon.builders.large.scale(root.widgetScale).build()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            StyledText {
                Layout.fillWidth: true
                text: root.player?.trackTitle || root.tr("Nothing playing", "Nada en reproducción", "Nichts wird abgespielt")
                font: Tokens.font.title.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                text: root.player?.trackArtist || root.tr("Unknown artist", "Artista desconocido", "Unbekannter Künstler")
                color: Colours.palette.m3onSurfaceVariant
                font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            StyledText {
                Layout.fillWidth: true
                visible: root.opts.showAlbum !== false && (root.player?.trackAlbum ?? "") !== ""
                text: root.player?.trackAlbum ?? ""
                color: Colours.palette.m3outline
                font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
                elide: Text.ElideRight
            }

            RowLayout {
                visible: root.opts.showControls !== false
                spacing: Tokens.spacing.small * root.widgetScale

                WidgetIconButton {
                    icon: "skip_previous"
                    widgetScale: root.widgetScale
                    disabled: !(root.player?.canGoPrevious ?? false)
                    onClicked: {
                        if (root.player?.canGoPrevious)
                            root.player.previous();
                    }
                }

                WidgetIconButton {
                    icon: root.playing ? "pause" : "play_arrow"
                    widgetScale: root.widgetScale
                    disabled: !(root.player?.canTogglePlaying ?? false)
                    onClicked: {
                        if (root.player?.canTogglePlaying)
                            root.player.togglePlaying();
                    }
                }

                WidgetIconButton {
                    icon: "skip_next"
                    widgetScale: root.widgetScale
                    disabled: !(root.player?.canGoNext ?? false)
                    onClicked: {
                        if (root.player?.canGoNext)
                            root.player.next();
                    }
                }
            }
        }
    }

    Item {
        Layout.fillWidth: true
        visible: root.opts.showProgress !== false
        implicitHeight: 14 * root.widgetScale

        StyledProgressBar {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            value: root.progress
            implicitHeight: 5 * root.widgetScale
            fgColour: root.accentColour
        }

        CustomMouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: mouse => {
                if (root.player?.canSeek && root.length > 0)
                    root.player.position = Math.max(0, Math.min(1, mouse.x / width)) * root.length;
            }
        }
    }
}
