// PS5 only: "Connect your controller", shown by lumen-installer-session
// before the power-on screen (start.qml). A DualSense paired with the PS5
// system software isn't paired with Linux, so this asks for PS + Create
// and moves on by itself once a controller works. The pairing is done by
// lumen-pad-pair.service, which reports through /run/lumen/pad-pair (see
// /usr/lib/lumen-ps5/pad-pair). Enter or Escape on a keyboard skips it.
// Needs QML_XHR_ALLOW_FILE_READ=1.
import QtQuick
import QtQuick.Window
// Relative so it resolves on the image, where this sits next to start.qml.
import "../../../etc/calamares/branding/lumen/components"

Window {
    id: win
    // Cover the screen even where fullscreen isn't honoured.
    width: Screen.width > 0 ? Screen.width : 1920
    height: Screen.height > 0 ? Screen.height : 1080
    visible: true
    visibility: Window.FullScreen
    color: Theme.bg0
    title: "Lumen OS"

    ViewSize {}

    property string state_: ""      // first word of /run/lumen/pad-pair
    property string padName: ""     // the rest, when there is one
    property bool done: false

    function finish() {
        if (done) return
        done = true
        fadeOut.start()
    }
    NumberAnimation { id: fadeOut; target: stage; property: "opacity"; to: 0; duration: 600
                      onFinished: Qt.exit(0) }

    function poll() {
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE) return
            const line = (xhr.responseText || "").trim()
            if (!line) return
            const space = line.indexOf(" ")
            state_ = space < 0 ? line : line.slice(0, space)
            padName = space < 0 ? "" : line.slice(space + 1)
            if (state_ === "connected" || state_ === "ready") doneTimer.start()
            else if (state_ === "none") finish()      // no Bluetooth adapter
        }
        xhr.open("GET", "file:///run/lumen/pad-pair")
        xhr.send()
    }
    Timer { interval: 700; running: !win.done; repeat: true; triggeredOnStart: true; onTriggered: win.poll() }
    // Show "Connected" for a moment before moving on.
    Timer { id: doneTimer; interval: 1800; onTriggered: win.finish() }

    Item {
        id: stage
        anchors.fill: parent
        focus: true
        Keys.onPressed: (event) => {
            if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Escape, Qt.Key_F10].indexOf(event.key) >= 0) {
                win.finish(); event.accepted = true;
            }
        }

        Backdrop { anchors.fill: parent }

        Text {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.leftMargin: Theme.gutter
            anchors.bottomMargin: Theme.rem(7.5)
            text: "Lumen OS"
            color: Theme.muted
            font.family: Theme.font
            font.pixelSize: Theme.smallSize
        }

        Column {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -Theme.rem(1.5)
            spacing: Theme.rem(2.4)

            // Controller outline with a light bar that pulses while searching
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: Theme.rem(11); height: Theme.rem(7)
                readonly property bool connected: win.state_ === "connected" || win.state_ === "ready"
                Rectangle {
                    id: body
                    anchors.fill: parent
                    radius: height / 2.4
                    color: Theme.glass
                    border.width: 2
                    border.color: Theme.stroke
                }
                Rectangle {
                    id: lightBar
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Theme.rem(0.9)
                    width: Theme.rem(4); height: Theme.rem(0.45); radius: height / 2
                    color: parent.connected ? Theme.accent : Theme.aurora2
                    SequentialAnimation on opacity {
                        running: !lightBar.parent.connected
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.2; duration: 220 }
                        NumberAnimation { to: 1.0; duration: 220 }
                        PauseAnimation { duration: 160 }
                    }
                }
                Row {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: Theme.rem(0.8)
                    spacing: Theme.rem(4.2)
                    Repeater {
                        model: 2
                        Rectangle { width: Theme.rem(1.6); height: width; radius: width / 2
                                    color: Theme.glassHi; border.width: 1; border.color: Theme.stroke }
                    }
                }
            }

            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Theme.rem(0.9)
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: win.state_ === "connected" || win.state_ === "ready"
                          ? qsTr("Controller connected")
                          : qsTr("Connect your controller")
                    color: Theme.text
                    font.family: Theme.font
                    font.pixelSize: Theme.rem(2.4)
                    font.weight: Font.Light
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    horizontalAlignment: Text.AlignHCenter
                    width: Theme.rem(34)
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                    text: {
                        if (win.state_ === "connected" || win.state_ === "ready")
                            return win.padName
                        if (win.state_ === "pairing")
                            return qsTr("Pairing %1…").arg(win.padName)
                        return qsTr("Hold the PS button and the Create button on your DualSense until the light bar flashes. "
                                    + "Or plug it in with a USB cable.")
                    }
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: Theme.bodySize
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Theme.rem(10)
            visible: win.state_ !== "connected" && win.state_ !== "ready"
            text: win.state_ === "" ? qsTr("Starting Bluetooth…") : qsTr("Looking for controllers…")
            color: Theme.faint
            font.family: Theme.font
            font.pixelSize: Theme.smallSize
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                NumberAnimation { to: 0.35; duration: 1200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
            }
        }

        // Hint bar
        Row {
            anchors.right: parent.right
            anchors.rightMargin: Theme.gutter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Theme.rem(1)
            height: Theme.rem(3.6)
            spacing: Theme.rem(2)
            PadHint { anchors.verticalCenter: parent.verticalCenter; button: "Enter"; label: qsTr("Skip")
                      onClicked: win.finish() }
        }
    }
}
