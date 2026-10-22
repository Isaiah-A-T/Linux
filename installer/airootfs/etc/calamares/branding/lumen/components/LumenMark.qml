// The Lumen mark from the shell's boot splash: an accent arc and an
// inner white arc spinning in opposite directions around a glowing
// accent core. "spinning: false" freezes it for small brand use.
import QtQuick

Item {
    id: mark
    property bool spinning: true
    property real outerAngle: 0
    property real innerAngle: 0
    implicitWidth: Theme.rem(7)
    implicitHeight: Theme.rem(7)

    // spin 1.2s var(--ease) and reverse 1.6s
    NumberAnimation on outerAngle {
        running: mark.spinning
        from: 0; to: 360; duration: 1200; loops: Animation.Infinite
        easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease
    }
    NumberAnimation on innerAngle {
        running: mark.spinning
        from: 360; to: 0; duration: 1600; loops: Animation.Infinite
        easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease
    }

    readonly property real s: Math.min(width, height)

    component Arc: Canvas {
        property color tint
        property real lineWidth
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var r = width / 2 - lineWidth / 2;
            ctx.strokeStyle = String(tint);
            ctx.lineWidth = lineWidth;
            // clip-path: polygon(50% 50%, 100% 0, 100% 100%) = the right
            // quarter of the ring.
            ctx.beginPath();
            ctx.arc(width / 2, height / 2, r, -Math.PI / 4, Math.PI / 4, false);
            ctx.stroke();
        }
    }

    Item {
        anchors.fill: parent
        rotation: mark.outerAngle
        Arc { tint: Theme.accent; lineWidth: mark.s * 0.05 }
    }
    Item {
        anchors.fill: parent
        anchors.margins: mark.s * 1.2 / 7
        rotation: mark.innerAngle
        Arc { tint: "white"; lineWidth: mark.s * 0.05 }
    }
    // Core with its 2rem glow
    Repeater {
        model: 6
        Rectangle {
            required property int index
            anchors.centerIn: parent
            width: core.width + (index + 1) * mark.s * 0.06
            height: width
            radius: width / 2
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16 * Math.pow(1 - index / 6, 2))
        }
    }
    Rectangle {
        id: core
        anchors.centerIn: parent
        width: mark.s * 1.8 / 7
        height: width
        radius: width / 2
        color: Theme.accent
    }
}
