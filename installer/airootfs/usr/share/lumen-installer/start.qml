// Live-ISO power-on screen, run by lumen-installer-session before
// Calamares. It mirrors the shell's boot splash and sign-in screen: the
// Lumen mark, a greeting that cycles through languages until A is
// pressed, then a choice of what to do. The choice is the exit code:
//   0  set up Lumen OS (start the installer)
//   10 try Lumen OS first (start the normal shell)
//   20 turn off
import QtQuick
import QtQuick.Window
// Relative so it resolves both on the live system and in the repo tree.
import "../../../etc/calamares/branding/lumen/components"

Window {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: Window.FullScreen
    color: Theme.bg0
    title: "Lumen OS"

    property bool started: false

    function finish(code) { exitTimer.code = code; fadeOut.start() }
    Timer { id: exitTimer; property int code: 0; interval: 10; onTriggered: Qt.exit(code) }
    NumberAnimation { id: fadeOut; target: stage; property: "opacity"; to: 0; duration: 600
                      onFinished: exitTimer.start() }

    Item {
        id: stage
        anchors.fill: parent

        Backdrop { anchors.fill: parent }

        // Clock and brand, placed like the sign-in screen
        Text {
            id: clock
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: Theme.gutter
            anchors.topMargin: Theme.rem(2.2)
            color: Theme.text
            font.family: Theme.font
            font.pixelSize: Theme.rem(1.6)
            font.weight: Font.Light
            function refresh() { text = Qt.formatTime(new Date(), "h:mm AP") }
            Component.onCompleted: refresh()
            Timer { interval: 5000; running: true; repeat: true; onTriggered: clock.refresh() }
        }
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

        // ---- Splash ---------------------------------------------------
        FocusScope {
            id: splash
            anchors.fill: parent
            visible: opacity > 0
            opacity: win.started ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 600 } }
            focus: !win.started

            readonly property var greetings: ["Hello", "Hola", "Bonjour", "Hallo", "Ciao", "Olá",
                                              "こんにちは", "안녕하세요", "Привет", "你好", "Merhaba", "Hej"]
            property int greetingIndex: 0

            function begin() { win.started = true; setup.forceActiveFocus(); cardsIn.restart() }
            Keys.onPressed: (event) => {
                if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_F10].indexOf(event.key) >= 0) {
                    begin(); event.accepted = true;
                }
            }
            MouseArea { anchors.fill: parent; onClicked: splash.begin() }

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -Theme.rem(2)
                spacing: Theme.rem(2.6)
                LumenMark {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Theme.rem(7); height: width
                }
                Text {
                    id: greeting
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: splash.greetings[splash.greetingIndex]
                    color: Theme.text
                    font.family: Theme.font
                    font.pixelSize: Theme.rem(2.4)
                    font.weight: Font.Light
                    Behavior on text {
                        SequentialAnimation {
                            NumberAnimation { target: greeting; property: "opacity"; to: 0; duration: 260 }
                            PropertyAction {}
                            NumberAnimation { target: greeting; property: "opacity"; to: 1; duration: 420 }
                        }
                    }
                }
            }
            Timer {
                running: splash.visible
                interval: 2200; repeat: true
                onTriggered: splash.greetingIndex = (splash.greetingIndex + 1) % splash.greetings.length
            }

            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Theme.rem(10)
                spacing: Theme.rem(0.7)
                Text { text: qsTr("Press"); color: Theme.text; font.family: Theme.font; font.pixelSize: Theme.rem(1.2)
                       anchors.verticalCenter: parent.verticalCenter }
                Rectangle {
                    width: Theme.rem(2.2); height: width; radius: width / 2
                    color: Theme.glyph
                    anchors.verticalCenter: parent.verticalCenter
                    Text { anchors.centerIn: parent; text: "A"; color: Theme.glyphText
                           font.family: Theme.font; font.pixelSize: Theme.rem(1); font.weight: Font.ExtraBold }
                }
                Text { text: qsTr("to begin"); color: Theme.text; font.family: Theme.font; font.pixelSize: Theme.rem(1.2)
                       anchors.verticalCenter: parent.verticalCenter }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 1200; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: 1200; easing.type: Easing.InOutSine }
                }
            }
        }

        // ---- Choice ---------------------------------------------------
        FocusScope {
            id: choice
            anchors.fill: parent
            visible: opacity > 0
            opacity: win.started ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 600 } }
            focus: win.started
            Keys.onEscapePressed: win.started = false

            Column {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -Theme.rem(1)
                spacing: Theme.rem(3)

                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: Theme.rem(0.8)
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: qsTr("What would you like to do?")
                        color: Theme.text
                        font.family: Theme.font
                        font.pixelSize: Theme.rem(2.4)
                        font.weight: Font.Light
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: qsTr("Lumen OS is running from your USB drive.")
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: Theme.bodySize
                    }
                }

                Row {
                    id: cards
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: Theme.rem(1.6)

                    component Card: Blade {
                        id: card
                        required property int order
                        property string glyph: ""
                        property string heading: ""
                        property string body: ""
                        property bool primary: false
                        property real enter: 1
                        width: Theme.rem(21)
                        height: Theme.rem(16)
                        focusScale: 1.06
                        sheen: true
                        opacity: enter
                        // .tile.focused: lift by 0.4rem; userIn: rise in
                        transform: Translate {
                            y: (card.highlighted ? -Theme.rem(0.4) : 0) + (1 - card.enter) * Theme.rem(3)
                            Behavior on y { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }
                        }
                        Column {
                            anchors.fill: parent
                            anchors.margins: Theme.rem(1.8)
                            spacing: Theme.rem(0.7)
                            Rectangle {
                                width: Theme.rem(3.6); height: width; radius: width / 2
                                color: card.primary ? Theme.accent : Theme.glassHi
                                border.width: card.primary ? 0 : 1
                                border.color: Theme.stroke
                                Text {
                                    anchors.centerIn: parent
                                    text: card.glyph
                                    color: card.primary ? Theme.accentText : Theme.text
                                    font.family: Theme.font
                                    font.pixelSize: Theme.rem(1.5)
                                    font.weight: Font.Bold
                                }
                            }
                            Item { width: 1; height: Theme.rem(1.4) }
                            Text {
                                width: parent.width
                                text: card.heading
                                wrapMode: Text.WordWrap
                                color: Theme.text
                                font.family: Theme.font
                                font.pixelSize: Theme.rem(1.5)
                                font.weight: Font.Bold
                            }
                            Text {
                                width: parent.width
                                text: card.body
                                wrapMode: Text.WordWrap
                                color: Theme.muted
                                font.family: Theme.font
                                font.pixelSize: Theme.smallSize
                                lineHeight: 1.35
                            }
                        }
                    }

                    Card {
                        id: setup
                        order: 0
                        primary: true
                        glyph: "↓"
                        heading: qsTr("Set up Lumen OS")
                        body: qsTr("Install to this console's drive. Takes about ten minutes.")
                        focus: true
                        KeyNavigation.right: tryIt
                        onActivated: win.finish(0)
                    }
                    Card {
                        id: tryIt
                        order: 1
                        glyph: "▶"
                        heading: qsTr("Try it first")
                        body: qsTr("Look around without changing anything. You can install from the dock later.")
                        KeyNavigation.left: setup
                        KeyNavigation.right: off
                        onActivated: win.finish(10)
                    }
                    Card {
                        id: off
                        order: 2
                        glyph: "⏻"
                        heading: qsTr("Turn off")
                        body: qsTr("Shut down now. Nothing on this console has been changed.")
                        KeyNavigation.left: tryIt
                        onActivated: win.finish(20)
                    }
                }
            }

            // userIn: cards rise in one after another
            SequentialAnimation {
                id: cardsIn
                ScriptAction { script: { setup.enter = 0; tryIt.enter = 0; off.enter = 0 } }
                ParallelAnimation {
                    NumberAnimation { target: setup; property: "enter"; to: 1; duration: 550; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
                    SequentialAnimation { PauseAnimation { duration: 70 }
                        NumberAnimation { target: tryIt; property: "enter"; to: 1; duration: 550; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade } }
                    SequentialAnimation { PauseAnimation { duration: 140 }
                        NumberAnimation { target: off; property: "enter"; to: 1; duration: 550; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade } }
                }
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
            PadHint { anchors.verticalCenter: parent.verticalCenter; button: "A"; label: qsTr("Select") }
            PadHint { anchors.verticalCenter: parent.verticalCenter; button: "B"; label: qsTr("Back")
                      visible: win.started; onClicked: win.started = false }
        }
    }
}
