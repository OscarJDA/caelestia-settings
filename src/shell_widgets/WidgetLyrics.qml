pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Caelestia.Config
import Caelestia.Services
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Lyrics", "Letras", "Songtext")
    iconName: "lyrics"
    cardWidth: 360

    readonly property int lineCount: Math.max(1, Math.min(9, Number(root.opts.lines) || 3))
    readonly property var player: Players.active
    readonly property string playerTitle: (root.player?.trackTitle ?? "").trim()
    readonly property string playerArtist: (root.player?.trackArtist ?? "").trim()
    readonly property bool trackMatches: root.player !== null && Lyrics.trackTitle === root.playerTitle && Lyrics.trackArtist === root.playerArtist

    // The running shell does not always re-evaluate bindings that depend on
    // Lyrics.hasLyrics, so mirror the flag from its change signal instead.
    property bool serviceHasLyrics: false

    readonly property var lines: root.trackMatches && root.serviceHasLyrics ? Lyrics.lyrics : []
    readonly property bool hasLines: root.lines.length > 0

    property real position: 0

    readonly property int currentIndex: root.hasLines ? Lyrics.indexForTime(root.position) : -1

    // Keep the lyrics service pointed at the active track.  This is done from a
    // timer instead of a property binding because setTrack() has side effects
    // and a binding that depends on the current position would reload the
    // track (and briefly clear the lyrics) every time the position changes.
    function syncTrack(): void {
        const p = root.player;
        if (p) {
            Lyrics.setTrack(root.playerArtist, root.playerTitle, p.trackAlbum, p.length);
        } else {
            Lyrics.clearTrack();
        }
        root.syncPosition();
    }

    function syncPosition(): void {
        root.position = root.player?.position ?? 0;
    }

    function windowStart(): int {
        if (!root.hasLines || root.lines.length === 0)
            return 0;
        const desired = Math.max(0, root.currentIndex - Math.floor(root.lineCount / 2));
        return Math.min(desired, Math.max(0, root.lines.length - root.lineCount));
    }

    Component.onCompleted: {
        root.serviceHasLyrics = Lyrics.hasLyrics;
        root.syncTrack();
    }

    Connections {
        target: Players

        function onActiveChanged(): void {
            root.syncTrack();
        }
    }

    Connections {
        target: root.player

        function onTrackChanged(): void {
            root.syncTrack();
        }

        function onLengthChanged(): void {
            root.syncTrack();
        }

        function onPositionChanged(): void {
            root.syncPosition();
        }
    }

    Connections {
        target: Lyrics

        function onHasLyricsChanged(): void {
            root.serviceHasLyrics = Lyrics.hasLyrics;
        }
    }

    // MPRIS only emits positionChanged on D-Bus updates and seeks, so the
    // position has to be sampled to keep the highlighted line in sync.
    Timer {
        interval: 250
        running: root.player !== null
        repeat: true
        triggeredOnStart: true
        onTriggered: root.syncPosition()
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2 * root.widgetScale

        Repeater {
            model: Math.min(root.lineCount, Math.max(0, root.lines.length - root.windowStart()))

            delegate: StyledText {
                required property int index

                readonly property int lineIndex: root.windowStart() + index
                readonly property bool active: lineIndex === root.currentIndex

                Layout.fillWidth: true
                text: root.lines[lineIndex] ?? ""
                color: active ? root.accentColour : Colours.palette.m3onSurfaceVariant
                opacity: active ? 1 : 0.65
                horizontalAlignment: root.opts.centered === false ? Text.AlignLeft : Text.AlignHCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font: Tokens.font.body.builders.medium.scale(root.widgetScale).build()
            }
        }
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.hasLines && root.opts.showTitle === true
        text: root.playerTitle + (root.playerArtist ? " · " + root.playerArtist : "")
        color: Colours.palette.m3outline
        horizontalAlignment: Text.AlignHCenter
        font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
        elide: Text.ElideRight
    }

    StyledText {
        Layout.fillWidth: true
        visible: !root.hasLines
        text: {
            if (!root.player)
                return root.tr("Nothing playing", "Nada en reproducción", "Nichts wird abgespielt");
            if (Lyrics.loading)
                return root.tr("Searching lyrics…", "Buscando letras…", "Suche Songtext…");
            return root.tr("No lyrics for this track", "Sin letras para esta pista", "Kein Songtext für diesen Titel");
        }
        color: Colours.palette.m3onSurfaceVariant
        horizontalAlignment: Text.AlignHCenter
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
