pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Caelestia.Config
import qs.components
import qs.services

WidgetCard {
    id: root

    title: tr("Notes", "Notas", "Notizen")
    iconName: "sticky_note_2"
    cardWidth: 300
    interactive: root.opts.openOnClick !== false
    onClicked: root.openNote()

    readonly property int maxLines: Math.max(1, Math.min(40, Number(root.opts.maxLines) || 6))
    readonly property string filePath: root.expand(root.opts.path ?? "~/.config/caelestia-settings/notes.txt")

    property string noteText: ""

    function expand(path: string): string {
        if (path.startsWith("~/"))
            return (Quickshell.env("HOME") ?? "") + path.slice(1);
        return path;
    }

    function openNote(): void {
        Quickshell.execDetached(["xdg-open", root.filePath]);
    }

    FileView {
        id: noteFile

        path: root.filePath
        watchChanges: true
        printErrors: false

        onFileChanged: reload()
        onLoaded: root.noteText = text().trim()
        onLoadFailed: root.noteText = ""
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.noteText !== ""
        text: {
            const lines = root.noteText.split(/\r?\n/);
            return lines.slice(0, root.maxLines).join("\n");
        }
        color: Colours.palette.m3onSurface
        wrapMode: Text.WordWrap
        maximumLineCount: root.maxLines
        elide: Text.ElideRight
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }

    StyledText {
        Layout.fillWidth: true
        visible: root.noteText === ""
        text: root.tr("Empty note — click to edit", "Nota vacía: haz clic para editar", "Leere Notiz – zum Bearbeiten klicken")
        color: Colours.palette.m3onSurfaceVariant
        font: Tokens.font.body.builders.small.scale(root.widgetScale).build()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Tokens.spacing.small

        Item {
            Layout.fillWidth: true
        }

        StyledText {
            text: root.tr("Open", "Abrir", "Öffnen")
            color: root.accentColour
            font: Tokens.font.label.builders.small.scale(root.widgetScale).build()
        }

        WidgetIconButton {
            icon: "edit_note"
            widgetScale: root.widgetScale
            onClicked: root.openNote()
        }
    }
}
