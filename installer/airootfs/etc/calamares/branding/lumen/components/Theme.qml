// Lumen OS installer design tokens, mirrored from the shell's
// shell/ui/css/lumen.css so setup looks like the console it installs.
//
// Sizes are in "rem" like the shell: designed at 1920x1080 where
// 1rem = 16px, scaling with the screen width (width / 120, clamped
// 10-32px). Use Theme.rem(n) for any length.
pragma Singleton
import QtQuick

QtObject {
    id: theme

    // Screen the installer runs on (gamescope's output under Lumen).
    readonly property real screenWidth: Qt.application.screens.length ? Qt.application.screens[0].width : 1920
    readonly property real screenHeight: Qt.application.screens.length ? Qt.application.screens[0].height : 1080
    readonly property real u: Math.max(10, Math.min(32, screenWidth / 120))
    function rem(n) { return Math.round(n * u) }

    // Colour tokens (lumen.css :root)
    readonly property color accent: "#3ee6a0"
    readonly property color accentText: "#04110b"
    readonly property color bg0: "#04060c"
    readonly property color bg1: "#0a0f1e"
    readonly property color glass: Qt.rgba(16 / 255, 22 / 255, 38 / 255, 0.62)
    readonly property color glassStrong: Qt.rgba(12 / 255, 16 / 255, 28 / 255, 0.9)
    readonly property color glassHi: Qt.rgba(1, 1, 1, 0.06)
    readonly property color stroke: Qt.rgba(1, 1, 1, 0.09)
    readonly property color text: "#eef2ff"
    readonly property color muted: "#98a2bd"
    readonly property color faint: "#5f6884"
    readonly property color danger: "#ff6b8b"
    readonly property color warning: "#ffb547"
    readonly property color glyph: "#dfe5f5"      // hint-bar button glyphs
    readonly property color glyphText: "#0b0f19"
    // Aurora wallpaper blobs
    readonly property color aurora2: "#4d63ff"
    readonly property color aurora3: "#b43cff"

    // Profile colours, same list and order as lumend/users.py so the
    // initial-letter avatar here matches the one on the sign-in screen.
    readonly property var profileColors: ["#3ee6a0", "#4da3ff", "#ff6b8b", "#ffb547", "#b48cff", "#36d6e7", "#ff8f5a"]
    function colorFor(name) {
        // int(md5(name), 16) % len, done digit by digit to stay exact.
        var h = Qt.md5(name), r = 0, n = profileColors.length;
        for (var i = 0; i < h.length; ++i) r = (r * 16 + parseInt(h[i], 16)) % n;
        return profileColors[r];
    }

    // Type (Inter, as in the shell)
    readonly property string font: "Inter"
    readonly property real heroSize: rem(3.6)
    readonly property real titleSize: rem(2.6)
    readonly property real kickerSize: rem(0.85)
    readonly property real bodySize: rem(1.05)
    readonly property real smallSize: rem(0.9)
    readonly property real titleSpacing: -0.03 * titleSize
    readonly property real kickerSpacing: 0.18 * kickerSize

    // Shapes
    readonly property real radius: rem(1.1)       // tiles, panels
    readonly property real radiusSmall: rem(0.7)  // list items, fields
    readonly property real radiusLarge: rem(1.6)  // dialogs, keyboard
    readonly property real buttonHeight: rem(3.2)
    readonly property real fieldHeight: rem(3.4)
    readonly property real gutter: rem(3.5)        // page side padding
    readonly property real barHeight: 64          // Calamares caps QML bars at 64px

    // Focus ring: 0.22rem accent ring 0.35rem outside the item, with a
    // 2.2rem glow at 55% that pulses to 3.2rem / 75% every 2.4s.
    readonly property real ringWidth: rem(0.22)
    readonly property real ringOffset: rem(0.35)
    readonly property real glow: rem(2.2)
    readonly property real glowPulse: rem(3.2)
    readonly property int pulseDuration: 2400

    // Motion
    readonly property int fast: 180
    readonly property int normal: 300
    readonly property int slow: 550
    // cubic-bezier(0.22, 1, 0.36, 1) and cubic-bezier(0.16, 1, 0.3, 1)
    readonly property var ease: [0.22, 1, 0.36, 1, 1, 1]
    readonly property var easeBlade: [0.16, 1, 0.3, 1, 1, 1]
}
