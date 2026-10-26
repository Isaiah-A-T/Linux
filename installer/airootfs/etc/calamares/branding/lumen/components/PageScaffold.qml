// Shared layout for every installer step: aurora backdrop, the title
// column on the left (kicker, title, subtitle, extras) and the step's
// controls in a glass panel on the right, like the shell's Settings.
//
// Controller keys handled here, for every QML step:
//   B (Escape)  back a step, or close the on-screen keyboard
//   Menu (F10)  next step
//   View (F9)   back a step
// The widget-based disk page gets Menu/View from calamares-navigation.qml.
import QtQuick
import QtQuick.Window
import io.calamares.ui 1.0

FocusScope {
    id: page
    property string kicker: ""
    property string title: ""
    property string subtitle: ""
    property Item initialFocus: null
    property OnScreenKeyboard keyboard: null
    property real split: 0.36
    property bool panel: true
    default property alias content: contentArea.data
    property alias aside: asideArea.data
    signal entered()

    anchors.fill: parent

    // Calamares only re-shows a step when the user goes back to it, so a
    // second activation always means "came back".
    property bool seen: false

    // Called from each page's onActivate(), which Calamares invokes when
    // the step is shown. Pulls keyboard focus into this page's window so
    // controller input lands here instead of the navigation bar.
    function activate() {
        bladeIn.back = seen;
        seen = true;
        bladeIn.restart();
        entered();
        if (Window.window) Window.window.requestActivate();
        focusTimer.restart();
    }
    Timer {
        id: focusTimer
        interval: 60
        onTriggered: (page.initialFocus || contentArea).forceActiveFocus()
    }

    Keys.onPressed: (event) => {
        if (keyboard && keyboard.shown) return;
        if (event.key === Qt.Key_Escape || event.key === Qt.Key_F9) {
            if (ViewManager.backEnabled) ViewManager.back();
            event.accepted = true;
        } else if (event.key === Qt.Key_F10) {
            if (ViewManager.nextEnabled) ViewManager.next();
            event.accepted = true;
        }
    }

    // The page sits between the 64px status and button bars.
    ViewSize { extraHeight: 2 * Theme.barHeight }
    Backdrop { anchors.fill: parent; originY: Theme.barHeight }

    Item {
        id: stage
        anchors.fill: parent
        transform: [
            Rotation { id: turn; origin.x: stage.width / 2; origin.y: stage.height / 2; axis { x: 0; y: 1; z: 0 } },
            Scale { id: zoom; origin.x: stage.width / 2; origin.y: stage.height / 2 },
            Translate { id: slide }
        ]

        Item {
            id: header
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: Theme.gutter
            width: (parent.width - Theme.gutter * 2) * page.split

            Column {
                id: titles
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -parent.height * 0.06
                spacing: Theme.rem(1)
                Text {
                    visible: text !== ""
                    text: page.kicker.toUpperCase()
                    color: Theme.accent
                    font.family: Theme.font
                    font.pixelSize: Theme.kickerSize
                    font.weight: Font.Bold
                    font.letterSpacing: Theme.kickerSpacing
                }
                Text {
                    width: parent.width
                    text: page.title
                    wrapMode: Text.WordWrap
                    color: Theme.text
                    font.family: Theme.font
                    font.pixelSize: Theme.titleSize
                    font.weight: Font.ExtraBold
                    font.letterSpacing: Theme.titleSpacing
                    lineHeight: 1.05
                }
                Text {
                    width: parent.width
                    visible: text !== ""
                    text: page.subtitle
                    wrapMode: Text.WordWrap
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: Theme.bodySize
                    lineHeight: 1.35
                }
                Item {
                    id: asideArea
                    width: parent.width
                    height: childrenRect.height
                }
            }
        }

        Panel {
            id: panelBox
            visible: page.panel
            anchors.fill: contentArea
            anchors.margins: -Theme.rem(1)
        }

        FocusScope {
            id: contentArea
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.rightMargin: Theme.gutter + Theme.rem(1)
            anchors.topMargin: Theme.rem(2.2)
            anchors.bottomMargin: Theme.rem(1.6)
            width: (parent.width - Theme.gutter * 2) * (1 - page.split) - Theme.rem(4)
            focus: true
        }
    }

    // The shell's page change ("blade in"): slides in from the right
    // turned slightly away, or from the left when going back.
    ParallelAnimation {
        id: bladeIn
        property bool back: false
        running: false
        NumberAnimation { target: stage; property: "opacity"; from: 0; to: 1; duration: Theme.slow
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
        NumberAnimation { target: slide; property: "x"; from: Theme.rem(bladeIn.back ? -12 : 14); to: 0; duration: Theme.slow
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
        NumberAnimation { target: turn; property: "angle"; from: bladeIn.back ? 12 : -14; to: 0; duration: Theme.slow
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
        NumberAnimation { target: zoom; properties: "xScale,yScale"; from: 0.96; to: 1; duration: Theme.slow
                          easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade }
    }
}
