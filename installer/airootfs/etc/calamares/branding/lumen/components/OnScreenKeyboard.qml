// The shell's on-screen keyboard (shell/ui/js/osk.js), for controller
// users:
//   D-pad move   A type   X delete   Y space   Menu done   B close
//   LB shift     RB symbols
// It edits whichever TextInput was passed to open().
import QtQuick

Item {
    id: osk
    property var target: null
    property string title: ""
    property bool shifted: false
    property bool symbols: false
    property bool numericOnly: false
    property int row: 1
    property int col: 0
    readonly property bool shown: target !== null
    signal closed()

    anchors.fill: parent
    visible: opacity > 0
    opacity: shown ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.normal } }
    z: 100

    readonly property var letters: [
        ["1","2","3","4","5","6","7","8","9","0"],
        ["q","w","e","r","t","y","u","i","o","p"],
        ["a","s","d","f","g","h","j","k","l"],
        ["z","x","c","v","b","n","m"],
        ["shift","#+=","space","del","done"]
    ]
    readonly property var symbolKeys: [
        ["1","2","3","4","5","6","7","8","9","0"],
        ["!","@","#","$","%","^","&","*","(",")"],
        ["-","_","=","+","[","]","{","}","/"],
        [".",",",";",":","'","\"","?"],
        ["shift","abc","space","del","done"]
    ]
    readonly property var digits: [
        ["1","2","3"], ["4","5","6"], ["7","8","9"], ["del","0","done"]
    ]
    readonly property var keys: numericOnly ? digits : (symbols ? symbolKeys : letters)

    function open(input, label, numeric) {
        target = input; title = label || ""; numericOnly = !!numeric;
        shifted = false; symbols = false;
        row = numericOnly ? 0 : 1; col = 0;
        grid.forceActiveFocus();
    }
    function close() {
        var t = target; target = null;
        if (t) t.forceActiveFocus();
        closed();
    }
    function type(ch) {
        if (!target) return;
        if (target.maximumLength > 0 && target.text.length >= target.maximumLength) return;
        target.insert(target.cursorPosition, ch);
        // Re-run validators and textEdited consumers the way typing would.
        target.textEdited();
    }
    function press(k) {
        if (!target) return;
        switch (k) {
        case "done": close(); return;
        case "del":
            if (target.cursorPosition > 0) {
                target.remove(target.cursorPosition - 1, target.cursorPosition);
                target.textEdited();
            }
            return;
        case "shift": shifted = !shifted; return;
        case "#+=": symbols = true; clampCol(); return;
        case "abc": symbols = false; clampCol(); return;
        case "space": type(" "); return;
        }
        type(shifted && !symbols ? k.toUpperCase() : k);
        if (shifted && !symbols) shifted = false;
    }
    function clampCol() { col = Math.min(col, keys[row].length - 1) }
    function caption(k) {
        switch (k) {
        case "shift": return "⇧";
        case "del": return "⌫";
        case "space": return qsTr("space");
        case "done": return qsTr("Done");
        }
        return shifted && !symbols && k.length === 1 ? k.toUpperCase() : k;
    }
    function keyWidth(k) {
        var u = Theme.rem(4.6);
        if (numericOnly) return Theme.rem(6.5);
        if (k === "space") return Theme.rem(22);
        if (k.length > 1) return Theme.rem(9);
        return u;
    }

    // Scrim behind the keyboard
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(4 / 255, 6 / 255, 12 / 255, 0.55)
        MouseArea { anchors.fill: parent; onClicked: osk.close() }
    }

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        // .osk: rises from below with the blade easing
        anchors.bottomMargin: osk.shown ? Theme.rem(1.2) : -height
        Behavior on anchors.bottomMargin { NumberAnimation { duration: 350; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeBlade } }
        width: Math.min(parent.width - Theme.rem(2), osk.numericOnly ? Theme.rem(24) : Theme.rem(70))
        height: content.implicitHeight + Theme.rem(2.4)
        radius: Theme.radiusLarge
        // glass-strong, made nearly opaque because there is no backdrop
        // blur here to keep the page behind it from showing through.
        color: Qt.rgba(12 / 255, 16 / 255, 28 / 255, 0.97)
        border.color: Theme.stroke
        border.width: 1

        Column {
            id: content
            x: Theme.rem(1.2)
            y: Theme.rem(1.2)
            width: parent.width - Theme.rem(2.4)
            spacing: Theme.rem(0.5)

            // .preview: what is being typed, with a blinking caret
            Rectangle {
                width: parent.width
                height: Theme.rem(3.2)
                radius: Theme.rem(0.8)
                color: Qt.rgba(0, 0, 0, 0.35)
                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: Theme.rem(1)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: !osk.target ? ""
                              : osk.target.echoMode === TextInput.Password
                                ? "●".repeat(osk.target.text.length) : osk.target.text
                        color: Theme.text
                        font.family: Theme.font
                        font.pixelSize: Theme.rem(1.2)
                    }
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 2; height: Theme.rem(1.5)
                        color: Theme.accent
                        SequentialAnimation on opacity {
                            running: osk.shown; loops: Animation.Infinite
                            PropertyAction { value: 1 } PauseAnimation { duration: 500 }
                            PropertyAction { value: 0 } PauseAnimation { duration: 500 }
                        }
                    }
                }
                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.rem(1)
                    anchors.verticalCenter: parent.verticalCenter
                    text: osk.title
                    color: Theme.faint
                    font.family: Theme.font
                    font.pixelSize: Theme.smallSize
                }
            }

            Item {
                id: grid
                width: parent.width
                height: rows.implicitHeight
                focus: osk.shown

                Column {
                    id: rows
                    width: parent.width
                    spacing: Theme.rem(0.5)
                    Repeater {
                        model: osk.keys.length
                        Row {
                            id: keyRow
                            required property int index
                            property int r: index
                            spacing: Theme.rem(0.5)
                            anchors.horizontalCenter: parent.horizontalCenter
                            Repeater {
                                model: osk.keys[keyRow.r]
                                Rectangle {
                                    id: key
                                    required property int index
                                    required property string modelData
                                    property bool current: osk.row === keyRow.r && osk.col === index
                                    property bool accentKey: modelData === "done"
                                    width: osk.keyWidth(modelData)
                                    height: Theme.rem(3.6)
                                    radius: Theme.rem(0.6)
                                    color: accentKey ? Theme.accent
                                         : current ? Qt.rgba(1, 1, 1, 0.22)
                                         : (modelData === "shift" && osk.shifted) ? Qt.rgba(1, 1, 1, 0.16)
                                         : Theme.glassHi
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    FocusRing { active: key.current; itemRadius: key.radius; glowSize: Theme.rem(1.6) }
                                    Text {
                                        anchors.centerIn: parent
                                        text: osk.caption(key.modelData)
                                        color: key.accentKey ? Theme.accentText : Theme.text
                                        font.family: Theme.font
                                        font.pixelSize: Theme.rem(1.15)
                                        font.weight: key.accentKey ? Font.Bold : Font.DemiBold
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: { osk.row = keyRow.r; osk.col = key.index; osk.press(key.modelData) }
                                    }
                                }
                            }
                        }
                    }
                }

                Keys.onPressed: (event) => {
                    switch (event.key) {
                    case Qt.Key_Left:  osk.col = (osk.col + osk.keys[osk.row].length - 1) % osk.keys[osk.row].length; break;
                    case Qt.Key_Right: osk.col = (osk.col + 1) % osk.keys[osk.row].length; break;
                    case Qt.Key_Up:
                        if (osk.row > 0) {
                            // Keep roughly the same horizontal position.
                            var f = (osk.col + 0.5) / osk.keys[osk.row].length;
                            osk.row--; osk.col = Math.floor(f * osk.keys[osk.row].length);
                        }
                        break;
                    case Qt.Key_Down:
                        if (osk.row < osk.keys.length - 1) {
                            var g = (osk.col + 0.5) / osk.keys[osk.row].length;
                            osk.row++; osk.col = Math.floor(g * osk.keys[osk.row].length);
                        }
                        break;
                    case Qt.Key_Return:
                    case Qt.Key_Enter: osk.press(osk.keys[osk.row][osk.col]); break;
                    case Qt.Key_Backspace: osk.press("del"); break;
                    case Qt.Key_Space: osk.press("space"); break;
                    case Qt.Key_Backtab: osk.shifted = !osk.shifted; break;
                    case Qt.Key_Tab: osk.press(osk.symbols ? "abc" : "#+="); break;
                    case Qt.Key_Escape:
                    case Qt.Key_F10: osk.close(); break;
                    default:
                        // A physical keyboard still works while the OSK is up.
                        if (event.text.length === 1 && event.text > " " && osk.target) osk.type(event.text);
                        else return;
                    }
                    event.accepted = true;
                }
            }

            Row {
                anchors.right: parent.right
                topPadding: Theme.rem(0.4)
                spacing: Theme.rem(2)
                PadHint { button: "A"; label: qsTr("Type") }
                PadHint { button: "X"; label: qsTr("Delete"); onClicked: osk.press("del") }
                PadHint { button: "Y"; label: qsTr("Space"); onClicked: osk.press("space") }
                PadHint { button: "LB"; label: qsTr("Shift"); visible: !osk.numericOnly; onClicked: osk.shifted = !osk.shifted }
                PadHint { button: "☰"; label: qsTr("Done"); onClicked: osk.close() }
            }
        }
    }
}
