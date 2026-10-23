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
    readonly property var lines: Lyrics.lyrics
    readonly property int currentIndex: Lyrics.hasLyrics ? Lyrics.indexForTime(root.player?.position ?? 0) : -1

    readonly property var player: Players.active

    // Keeps the lyrics service pointed at the active track.
    readonly property var tracker: {
        const p = root.player;
        if (p)
            Lyrics.setTrack(p.trackArtist, p.trackTitle, p.trackAlbum, p.length);
        else
            Lyrics.clearTrack();
        return root.currentIndex;
    }

    function windowStart(): int {
        if (!Lyrics.hasLyrics || root.lines.length === 0)
            return 0;
        const desired = Math.max(0, root.currentIndex - Math.floor(root.lineCount / 2));
        return Math.min(desired, Math.max(0, root.lines.length - root.lineCount));
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
        visible: Lyrics.hasLyrics && root.opts.showTitle === true
        text: (root.player?.trackTitle ?? "") + (root.player?.trackArtist ? " · " + root.player.trackArtist : "")
        color: Colours.palette.m3outline
        horizontalAlignment: Text.AlignHCenter
        font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
        elide: Text.ElideRight
    }

    StyledText {
        Layout.fillWidth: true
        visible: !Lyrics.hasLyrics
        text: Lyrics.loading ? root.tr("Searching lyrics…", "Buscando letras…", "Suche Songtext…") : root.tr("No lyrics for this track", "Sin letras para esta pista", "Kein Songtext für diesen Titel")
        color: Colours.palette.m3onSurfaceVariant
        horizontalAlignment: Text.AlignHCenter
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }
}
