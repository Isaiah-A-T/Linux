// Top bar, like the shell's: brand on the left, one pip per setup step
// in the middle (the current one stretches into a labelled accent pill)
// and the clock on the right. Calamares caps this bar at 64px.
import io.calamares.ui 1.0
import io.calamares.core 1.0

import QtQuick
import "components"

Item {
    id: bar
    height: Theme.barHeight
    implicitHeight: Theme.barHeight

    ViewSize { useHeight: false }
    Backdrop { anchors.fill: parent; originY: 0 }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.rem(0.7)
        LumenMark { width: Theme.rem(1.9); height: width; spinning: false; anchors.verticalCenter: parent.verticalCenter }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: qsTr("%1 Setup").arg(Branding.string(Branding.ProductName))
            color: Theme.text
            font.family: Theme.font
            font.pixelSize: Theme.bodySize
            font.weight: Font.Bold
        }
    }

    Row {
        anchors.centerIn: parent
        spacing: Theme.rem(0.55)
        Repeater {
            model: ViewManager
            Rectangle {
                required property int index
                required property string display
                property bool current: index === ViewManager.currentStepIndex
                property bool done: index < ViewManager.currentStepIndex
                anchors.verticalCenter: parent.verticalCenter
                height: current ? Theme.rem(1.8) : Theme.rem(0.55)
                width: current ? label.implicitWidth + Theme.rem(1.8) : Theme.rem(0.55)
                radius: height / 2
                color: current ? Theme.accent : done ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.55)
                                                     : Qt.rgba(1, 1, 1, 0.18)
                Behavior on width { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }
                Behavior on height { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }
                Behavior on color { ColorAnimation { duration: Theme.normal } }
                Text {
                    id: label
                    anchors.centerIn: parent
                    opacity: parent.current ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.normal } }
                    text: display
                    color: Theme.accentText
                    font.family: Theme.font
                    font.pixelSize: Theme.rem(0.8)
                    font.weight: Font.ExtraBold
                }
            }
        }
    }

    Text {
        id: clock
        anchors.right: parent.right
        anchors.rightMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text
        font.family: Theme.font
        font.pixelSize: Theme.rem(1.6)
        font.weight: Font.Light
        function refresh() { text = Qt.formatTime(new Date(), "h:mm AP") }
        Component.onCompleted: refresh()
        Timer { interval: 5000; running: true; repeat: true; onTriggered: clock.refresh() }
    }
}
