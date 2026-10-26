// Shown while files are copied (slideshowAPI 2). Calamares draws its own
// progress bar and status text under this; see stylesheet.qss.
import QtQuick
import "components"

Item {
    id: show
    property bool active: false
    property int slide: 0

    // Calamares' progress bar sits under the slideshow; size by width.
    ViewSize { useHeight: false }

    function onActivate() { active = true; slide = 0 }
    function onLeave() { active = false }

    readonly property var slides: [
        { kicker: qsTr("SETTING UP"), title: qsTr("Getting everything ready"),
          body: qsTr("This takes a few minutes. You can put the controller down; we'll let you know when it's done.") },
        { kicker: qsTr("HOME"), title: qsTr("Your 15 most recent, front and center"),
          body: qsTr("Home keeps the games and apps you use most within one press. Everything else lives in your Library.") },
        { kicker: qsTr("LIBRARY"), title: qsTr("Every launcher, one library"),
          body: qsTr("Sign in to Steam, GOG, Epic and more. Their games show up side by side, ready to download with Proton set up for you.") },
        { kicker: qsTr("QUICK SETTINGS"), title: qsTr("Wi-Fi and Bluetooth, one press away"),
          body: qsTr("The top bar puts the things you change often first, so pairing a controller never means digging through menus.") },
        { kicker: qsTr("STORE"), title: qsTr("Apps from Flathub and Snap"),
          body: qsTr("Browse desktop apps with full descriptions and screenshots, and install them right from the couch.") }
    ]

    Backdrop { anchors.fill: parent; originY: Theme.barHeight }

    Timer {
        running: show.active
        interval: 7000; repeat: true
        onTriggered: show.slide = (show.slide + 1) % show.slides.length
    }

    // Spinning ring, so there is always visible motion even when a step
    // takes a while without moving the progress bar.
    LumenMark {
        id: spinner
        width: Theme.rem(7); height: width
        spinning: show.active
        anchors.left: parent.left
        anchors.leftMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
    }

    Item {
        id: card
        anchors.left: spinner.right
        anchors.leftMargin: Theme.rem(3)
        anchors.right: parent.right
        anchors.rightMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
        height: Theme.rem(16)

        Repeater {
            model: show.slides
            Column {
                required property int index
                required property var modelData
                width: card.width
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.rem(1)
                opacity: index === show.slide ? 1 : 0
                visible: opacity > 0
                transform: Translate { x: index === show.slide ? 0 : Theme.rem(2.5)
                    Behavior on x { NumberAnimation { duration: Theme.slow; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade } } }
                Behavior on opacity { NumberAnimation { duration: Theme.slow } }
                Text {
                    text: modelData.kicker
                    color: Theme.accent
                    font.family: Theme.font; font.pixelSize: Theme.kickerSize
                    font.weight: Font.Bold; font.letterSpacing: Theme.kickerSpacing
                }
                Text {
                    width: parent.width
                    text: modelData.title
                    wrapMode: Text.WordWrap
                    color: Theme.text
                    font.family: Theme.font; font.pixelSize: Theme.titleSize; font.weight: Font.ExtraBold
                    font.letterSpacing: Theme.titleSpacing
                }
                Text {
                    width: Math.min(parent.width, Theme.rem(46))
                    text: modelData.body
                    wrapMode: Text.WordWrap
                    color: Theme.muted
                    font.family: Theme.font; font.pixelSize: Theme.rem(1.2)
                    lineHeight: 1.35
                }
            }
        }
    }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.rem(1.5)
        spacing: Theme.rem(0.55)
        Repeater {
            model: show.slides.length
            Rectangle {
                required property int index
                width: index === show.slide ? Theme.rem(1.8) : Theme.rem(0.55); height: Theme.rem(0.55); radius: height / 2
                color: index === show.slide ? Theme.accent : Qt.rgba(1, 1, 1, 0.18)
                Behavior on width { NumberAnimation { duration: Theme.normal } }
            }
        }
    }
}
