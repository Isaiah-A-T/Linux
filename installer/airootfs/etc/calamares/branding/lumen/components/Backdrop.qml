// The shell's animated "aurora" wallpaper: three large soft blobs
// (accent, blue, violet) drifting slowly, under a top-lit vignette.
//
// Calamares draws the top bar, each page and the bottom bar in separate
// windows, so every Backdrop lays its blobs out in whole-window
// coordinates (originY = where this item sits in the window) and derives
// the drift from the wall clock. The pieces then line up into one
// continuous background.
import QtQuick

Rectangle {
    id: root
    color: Theme.bg0
    clip: true

    property real originY: 0
    property real intensity: 1.0
    readonly property real sw: Theme.viewW
    readonly property real sh: Theme.viewH
    readonly property real vmax: Math.max(sw, sh) / 100
    property real now: Date.now()

    FrameAnimation {
        running: root.visible
        onTriggered: root.now = Date.now()
    }

    // CSS "ease-in-out infinite alternate" over `period` seconds, with
    // a negative start delay: 0 -> 1 -> 0 ...
    function swing(period, delay) {
        var t = ((now / 1000 + delay) % (2 * period)) / period;
        var p = t <= 1 ? t : 2 - t;
        return 0.5 - 0.5 * Math.cos(Math.PI * p);
    }

    component Blob: Canvas {
        id: blob
        property color tint
        property real alpha: 0.5
        property real baseX: 0
        property real baseY: 0
        property real period: 38
        property real delay: 0
        readonly property real k: root.swing(period, delay)
        width: 70 * root.vmax
        height: width
        x: baseX + k * 14 * root.vmax
        y: baseY + k * 10 * root.vmax - root.originY
        scale: 1 + 0.2 * k
        opacity: 0.5 * root.intensity
        renderTarget: Canvas.Image
        onWidthChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var r = width / 2;
            // radial-gradient(circle, tint alpha, transparent 65%) blurred
            // by 8vmax: approximated with a longer, eased falloff.
            var g = ctx.createRadialGradient(r, r, 0, r, r, r);
            g.addColorStop(0.0, Qt.rgba(tint.r, tint.g, tint.b, alpha));
            g.addColorStop(0.35, Qt.rgba(tint.r, tint.g, tint.b, alpha * 0.7));
            g.addColorStop(0.65, Qt.rgba(tint.r, tint.g, tint.b, alpha * 0.25));
            g.addColorStop(1.0, Qt.rgba(tint.r, tint.g, tint.b, 0));
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, width, height);
        }
    }

    Blob { tint: Theme.accent; alpha: 0.55; baseX: -20 * root.vmax; baseY: -30 * root.vmax; period: 38 }
    Blob { tint: Theme.aurora2; alpha: 0.5; baseX: root.sw - 45 * root.vmax; baseY: -10 * root.vmax; period: 46; delay: 12 }
    Blob { tint: Theme.aurora3; alpha: 0.35; baseX: 20 * root.vmax; baseY: root.sh - 25 * root.vmax; period: 52; delay: 20 }

    // radial-gradient(120% 90% at 50% 0%, transparent 30%, rgba(4,6,12,.85))
    Canvas {
        id: shade
        x: 0
        y: -root.originY
        width: root.sw
        height: root.sh
        renderTarget: Canvas.Image
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var rx = width * 1.2, ry = height * 0.9;
            ctx.save();
            ctx.translate(width / 2, 0);
            ctx.scale(1, ry / rx);
            var g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
            g.addColorStop(0.3, Qt.rgba(4 / 255, 6 / 255, 12 / 255, 0));
            g.addColorStop(1.0, Qt.rgba(4 / 255, 6 / 255, 12 / 255, 0.85));
            ctx.fillStyle = g;
            ctx.fillRect(-width, 0, width * 2, height * rx / ry);
            ctx.restore();
        }
    }
}
