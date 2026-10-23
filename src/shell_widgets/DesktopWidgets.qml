pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Caelestia.Config
import qs.components.containers
import qs.services
import "WidgetCatalog.js" as Catalog

// Interactive desktop widgets live in their own Bottom-layer surface so they
// sit above the wallpaper but below normal windows. The input mask is limited
// to the nine placement zones, keeping the rest of the desktop clickable.
Variants {
    model: Screens.screens

    StyledWindow {
        id: win

        required property ShellScreen modelData

        screen: modelData
        name: "widgets"
        WlrLayershell.layer: WlrLayer.Bottom
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        focusable: false
        color: "transparent"
        surfaceFormat.opaque: false

        anchors.top: true
        anchors.bottom: true
        anchors.left: true
        anchors.right: true

        property var rawConfig: null

        readonly property var settings: win.normalize(win.rawConfig)
        readonly property var global: settings.global
        readonly property real edgeMargin: Math.max(0, global.edgeMargin ?? 28)
        readonly property real gap: Math.max(0, global.gap ?? 16)
        readonly property real barWidth: Tokens.sizes.bar.innerWidth + Tokens.padding.large
        readonly property real leftMargin: edgeMargin + barWidth

        function defaultConfig(): var {
            const clock = Catalog.defaults("clock");
            const system = Catalog.defaults("system");
            const weather = Catalog.defaults("weather");
            const media = Catalog.defaults("media");
            const calendar = Catalog.defaults("calendar");

            clock.corner = "top-center";
            system.corner = "top-right";
            weather.corner = "bottom-right";
            media.corner = "bottom-left";
            calendar.corner = "bottom-center";

            return {
                version: 2,
                global: {
                    cardStyle: "material",
                    opacity: 1.0,
                    edgeMargin: 28,
                    gap: 16,
                    accent: "auto"
                },
                widgets: {
                    "clock-1": clock,
                    "system-1": system,
                    "weather-1": weather,
                    "media-1": media,
                    "calendar-1": calendar
                }
            };
        }

        function migrateV1(widgets: var): var {
            const migrated = {};
            let index = 0;
            for (const id in widgets) {
                if (!Catalog.has(id))
                    continue;
                const old = widgets[id] ?? ({});
                const options = Object.assign({}, old);
                delete options.enabled;
                delete options.corner;
                delete options.scale;
                delete options.order;
                migrated[`${id}-1`] = {
                    type: id,
                    enabled: old.enabled !== false,
                    corner: old.corner,
                    order: index++,
                    scale: old.scale ?? 1,
                    options: options
                };
            }

            if (!migrated["clock-1"])
                migrated["clock-1"] = Catalog.defaults("clock");

            return migrated;
        }

        function normalize(raw: var): var {
            const source = (raw && typeof raw === "object" && !Array.isArray(raw)) ? raw : ({});
            const isCurrent = source.version === 2;
            let widgets = source.widgets;

            if (!isCurrent)
                widgets = win.migrateV1((widgets && typeof widgets === "object") ? widgets : ({}));

            if (!widgets || typeof widgets !== "object" || Array.isArray(widgets))
                widgets = ({});

            if (!isCurrent && Object.keys(widgets).length === 0) {
                const fallback = win.defaultConfig();
                widgets = fallback.widgets;
            }

            const clean = {};
            for (const id in widgets) {
                const stored = widgets[id] ?? ({});
                const type = stored.type ?? id;
                if (!Catalog.has(type))
                    continue;
                const base = Catalog.defaults(type);
                clean[id] = {
                    id: id,
                    type: type,
                    enabled: stored.enabled !== false,
                    corner: win.validCorner(stored.corner) ? stored.corner : base.corner,
                    order: Number.isFinite(stored.order) ? stored.order : 0,
                    scale: Math.max(0.5, Math.min(3, Number(stored.scale) || 1)),
                    options: Object.assign({}, base.options, stored.options ?? ({}))
                };
            }

            const defaults = win.defaultConfig().global;
            return {
                version: 2,
                global: {
                    cardStyle: source.global?.cardStyle ?? defaults.cardStyle,
                    opacity: Math.max(0, Math.min(1, Number(source.global?.opacity ?? defaults.opacity))),
                    edgeMargin: Math.max(0, Number(source.global?.edgeMargin ?? defaults.edgeMargin)),
                    gap: Math.max(0, Number(source.global?.gap ?? defaults.gap)),
                    accent: source.global?.accent ?? defaults.accent
                },
                widgets: clean
            };
        }

        function validCorner(corner: string): bool {
            return ["top-left", "top-center", "top-right", "middle-left", "middle-center", "middle-right", "bottom-left", "bottom-center", "bottom-right"].includes(corner);
        }

        function widgetsAt(corner: string): var {
            const result = [];
            const widgets = win.settings.widgets;
            for (const id of Object.keys(widgets)) {
                const widget = widgets[id];
                if (widget.enabled && widget.corner === corner)
                    result.push(widget);
            }
            result.sort((a, b) => a.order - b.order);
            return result;
        }

        function widgetSource(type: string): url {
            const file = Catalog.componentFor(type);
            return file === "" ? "" : Qt.resolvedUrl(file);
        }

        FileView {
            id: configFile

            path: `${Quickshell.env("XDG_CONFIG_HOME") || (Quickshell.env("HOME") + "/.config")}/caelestia-settings/desktop_widgets.json`
            watchChanges: true
            printErrors: false

            onFileChanged: reload()
            onLoaded: {
                try {
                    win.rawConfig = JSON.parse(text());
                } catch (error) {
                    console.warn("Invalid desktop_widgets.json:", error);
                    win.rawConfig = null;
                }
            }
            onLoadFailed: error => {
                if (error === FileViewError.FileNotFound)
                    win.rawConfig = null;
            }
        }

        mask: Region {
            Region {
                x: zoneTopLeft.x
                y: zoneTopLeft.y
                width: zoneTopLeft.width
                height: zoneTopLeft.height
            }
            Region {
                x: zoneTopCenter.x
                y: zoneTopCenter.y
                width: zoneTopCenter.width
                height: zoneTopCenter.height
            }
            Region {
                x: zoneTopRight.x
                y: zoneTopRight.y
                width: zoneTopRight.width
                height: zoneTopRight.height
            }
            Region {
                x: zoneMiddleLeft.x
                y: zoneMiddleLeft.y
                width: zoneMiddleLeft.width
                height: zoneMiddleLeft.height
            }
            Region {
                x: zoneMiddleCenter.x
                y: zoneMiddleCenter.y
                width: zoneMiddleCenter.width
                height: zoneMiddleCenter.height
            }
            Region {
                x: zoneMiddleRight.x
                y: zoneMiddleRight.y
                width: zoneMiddleRight.width
                height: zoneMiddleRight.height
            }
            Region {
                x: zoneBottomLeft.x
                y: zoneBottomLeft.y
                width: zoneBottomLeft.width
                height: zoneBottomLeft.height
            }
            Region {
                x: zoneBottomCenter.x
                y: zoneBottomCenter.y
                width: zoneBottomCenter.width
                height: zoneBottomCenter.height
            }
            Region {
                x: zoneBottomRight.x
                y: zoneBottomRight.y
                width: zoneBottomRight.width
                height: zoneBottomRight.height
            }
        }

        component WidgetColumn: Column {
            id: column

            required property string corner

            readonly property var itemsAt: win.widgetsAt(column.corner)

            width: {
                let widest = 0;
                for (const item of column.itemsAt)
                    widest = Math.max(widest, Catalog.widthFor(item.type) * (item.scale ?? 1));
                return widest;
            }
            
            height: implicitHeight
            spacing: win.gap

            Repeater {
                model: column.itemsAt

                delegate: Item {
                    id: host

                    required property var modelData

                    implicitWidth: loader.item ? loader.item.implicitWidth : 0
                    implicitHeight: loader.item ? loader.item.implicitHeight : 0
                    width: implicitWidth
                    height: implicitHeight

                    Loader {
                        id: loader

                        anchors.fill: parent

                        Component.onCompleted: loader.setSource(win.widgetSource(host.modelData.type), {
                            widgetConfig: host.modelData,
                            globalConfig: win.global
                        })
                    }
                }
            }
        }

        WidgetColumn {
            id: zoneTopLeft

            corner: "top-left"
            x: win.leftMargin
            y: win.edgeMargin
        }

        WidgetColumn {
            id: zoneTopCenter

            corner: "top-center"
            x: (win.width - width) / 2
            y: win.edgeMargin
        }

        WidgetColumn {
            id: zoneTopRight

            corner: "top-right"
            x: win.width - width - win.edgeMargin
            y: win.edgeMargin
        }

        WidgetColumn {
            id: zoneMiddleLeft

            corner: "middle-left"
            x: win.leftMargin
            y: (win.height - height) / 2
        }

        WidgetColumn {
            id: zoneMiddleCenter

            corner: "middle-center"
            x: (win.width - width) / 2
            y: (win.height - height) / 2
        }

        WidgetColumn {
            id: zoneMiddleRight

            corner: "middle-right"
            x: win.width - width - win.edgeMargin
            y: (win.height - height) / 2
        }

        WidgetColumn {
            id: zoneBottomLeft

            corner: "bottom-left"
            x: win.leftMargin
            y: win.height - height - win.edgeMargin
        }

        WidgetColumn {
            id: zoneBottomCenter

            corner: "bottom-center"
            x: (win.width - width) / 2
            y: win.height - height - win.edgeMargin
        }

        WidgetColumn {
            id: zoneBottomRight

            corner: "bottom-right"
            x: win.width - width - win.edgeMargin
            y: win.height - height - win.edgeMargin
        }
    }
}
