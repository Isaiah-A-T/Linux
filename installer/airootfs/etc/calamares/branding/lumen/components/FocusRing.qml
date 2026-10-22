// Controller-focus highlight from the shell (.ring.focused): a 0.22rem
// accent ring 0.35rem outside the item and a soft accent glow that
// pulses every 2.4s. Put it inside the focusable item.
import QtQuick

Item {
    id: ring
    property bool active: false
    property real itemRadius: Theme.radius
    property real glowSize: Theme.glow
    property real glowAlpha: 0.55
    readonly property real outerRadius: itemRadius + Theme.ringOffset

    anchors.fill: parent
    anchors.margins: -Theme.ringOffset
    opacity: active ? 1 : 0
    scale: active ? 1 : 0.97
    visible: opacity > 0
    z: -1
    Behavior on opacity { NumberAnimation { duration: Theme.fast } }
    Behavior on scale { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }

    SequentialAnimation {
        running: ring.active
        loops: Animation.Infinite
        PauseAnimation { duration: 300 }
        ParallelAnimation {
            NumberAnimation { target: ring; property: "glowSize"; to: Theme.glowPulse; duration: Theme.pulseDuration / 2; easing.type: Easing.InOutQuad }
            NumberAnimation { target: ring; property: "glowAlpha"; to: 0.75; duration: Theme.pulseDuration / 2; easing.type: Easing.InOutQuad }
        }
        ParallelAnimation {
            NumberAnimation { target: ring; property: "glowSize"; to: Theme.glow; duration: Theme.pulseDuration / 2; easing.type: Easing.InOutQuad }
            NumberAnimation { target: ring; property: "glowAlpha"; to: 0.55; duration: Theme.pulseDuration / 2; easing.type: Easing.InOutQuad }
        }
    }

    // box-shadow blur, approximated by stacked rings fading outwards
    // (shader effects are not available in every renderer).
    Repeater {
        model: 9
        Rectangle {
            required property int index
            readonly property real step: ring.glowSize / 9 / 2
            anchors.fill: parent
            anchors.margins: -(index + 1) * step
            radius: ring.outerRadius + (index + 1) * step
            color: "transparent"
            border.width: step + 0.5
            border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b,
                                  ring.glowAlpha * 0.32 * Math.pow(1 - index / 9, 2))
        }
    }
    Rectangle {
        anchors.fill: parent
        radius: ring.outerRadius
        color: "transparent"
        border.width: Theme.ringWidth
        border.color: Theme.accent
    }
}
