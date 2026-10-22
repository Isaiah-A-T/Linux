// A focusable surface. "glass" makes it a card (translucent panel with a
// 1px stroke, like the shell's tiles); otherwise it is a list row that
// only lights up when focused. Focus shows the shell's ring and glow.
import QtQuick

Rectangle {
    id: blade
    property bool selected: false
    property bool highlighted: activeFocus
    property bool glass: true
    property real focusScale: 1.0
    property bool sheen: false
    signal activated()

    radius: glass ? Theme.radius : Theme.radiusSmall
    color: glass ? Theme.glass : "transparent"
    border.width: glass ? 1 : 0
    border.color: Theme.stroke
    scale: highlighted ? focusScale : 1.0
    activeFocusOnTab: true
    Behavior on scale { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }

    // :hover / .focused background
    Rectangle {
        anchors.fill: parent
        radius: blade.radius
        color: Theme.glassHi
        opacity: blade.highlighted || mouse.containsMouse ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    // One white sweep across the surface when it gains focus.
    Item {
        anchors.fill: parent
        clip: true
        visible: blade.sheen
        Rectangle {
            id: shine
            width: parent.width * 0.6
            height: parent.height * 2
            y: -parent.height / 2
            x: -width * 1.5
            rotation: 20
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.12) }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        NumberAnimation {
            id: shineAnim
            target: shine; property: "x"
            from: -shine.width * 1.5; to: blade.width * 1.2
            duration: 900; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease
        }
    }
    onHighlightedChanged: if (highlighted && sheen) shineAnim.restart()

    FocusRing { active: blade.highlighted; itemRadius: blade.radius }

    Keys.onReturnPressed: activated()
    Keys.onEnterPressed: activated()
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { blade.forceActiveFocus(); blade.activated() }
    }
}
