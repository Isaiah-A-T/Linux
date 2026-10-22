// Last step: success (restart into the new system) or failure details.
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick
import QtQuick.Window
import "components"

FocusScope {
    id: root
    function onActivate() {
        if (Window.window) Window.window.requestActivate();
        (config.failed ? quitButton : restartButton).forceActiveFocus();
        rise.restart();
    }
    function onLeave() {}

    Backdrop { anchors.fill: parent; originY: Theme.barHeight }

    Column {
        id: body
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -Theme.rem(2)
        width: Math.min(parent.width - 2 * Theme.gutter, Theme.rem(54))
        spacing: Theme.rem(1.5)
        transform: Translate { id: lift }

        LumenMark {
            visible: !config.failed
            anchors.horizontalCenter: parent.horizontalCenter
            width: Theme.rem(7); height: width
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: config.failed ? qsTr("Setup didn't finish") : qsTr("You're all set")
            color: config.failed ? Theme.danger : Theme.text
            font.family: Theme.font
            font.pixelSize: Theme.heroSize
            font.weight: Font.ExtraBold
            font.letterSpacing: -0.03 * Theme.heroSize
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            text: config.failed
                  ? config.failureMessage
                  : qsTr("%1 is installed. Remove the USB drive, then restart to sign in for the first time.")
                        .arg(Branding.string(Branding.ProductName))
            color: Theme.muted
            font.family: Theme.font
            font.pixelSize: Theme.rem(1.2)
            lineHeight: 1.35
        }
        Rectangle {
            visible: config.failed && config.failureDetails !== ""
            width: parent.width
            height: Math.min(Theme.rem(14), details.implicitHeight + Theme.rem(2))
            radius: Theme.radiusSmall
            color: Theme.glass
            border.color: Theme.stroke
            clip: true
            Text {
                id: details
                anchors.fill: parent
                anchors.margins: Theme.rem(1)
                text: config.failureDetails
                wrapMode: Text.WrapAnywhere
                color: Theme.muted
                font.family: "monospace"
                font.pixelSize: Theme.smallSize
            }
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.rem(1)
            topPadding: Theme.rem(1)
            ConsoleButton {
                id: restartButton
                visible: !config.failed
                primary: true
                text: qsTr("Restart now")
                KeyNavigation.right: quitButton
                onActivated: config.doRestart(true)
            }
            ConsoleButton {
                id: quitButton
                text: config.failed ? qsTr("Close setup") : qsTr("Keep using the live system")
                KeyNavigation.left: restartButton
                onActivated: ViewManager.quit()
            }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: config.failed
            text: qsTr("The full log is in /root/.cache/calamares/session.log")
            color: Theme.faint
            font.family: Theme.font
            font.pixelSize: Theme.smallSize
        }
    }

    // .sheet entrance: rise from +6% and scale up slightly
    ParallelAnimation {
        id: rise
        NumberAnimation { target: body; property: "opacity"; from: 0; to: 1; duration: 450 }
        NumberAnimation { target: lift; property: "y"; from: root.height * 0.06; to: 0; duration: 450
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: Theme.gutter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.rem(1.2)
        spacing: Theme.rem(2)
        PadHint { button: "A"; label: qsTr("Select") }
    }
}
