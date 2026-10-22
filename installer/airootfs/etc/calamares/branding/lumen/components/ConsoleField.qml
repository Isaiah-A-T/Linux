// Text entry, styled like the shell's .field. With a controller, focus
// it and press A to open the on-screen keyboard; with a physical
// keyboard just type.
import QtQuick

Item {
    id: field
    property alias text: input.text
    property alias echoMode: input.echoMode
    property alias validator: input.validator
    property alias maximumLength: input.maximumLength
    property alias inputMethodHints: input.inputMethodHints
    property string label: ""
    property string placeholder: ""
    property string status: ""          // non-empty shows below the field
    property bool statusIsError: true
    property var keyboard: null         // an OnScreenKeyboard on the page
    property bool numeric: false
    readonly property bool acceptable: input.acceptableInput
    signal edited()

    implicitHeight: col.implicitHeight
    implicitWidth: Theme.rem(26)
    activeFocusOnTab: true
    onActiveFocusChanged: if (activeFocus) input.forceActiveFocus()

    function openKeyboard() {
        if (keyboard) keyboard.open(input, label, numeric)
    }

    Column {
        id: col
        width: parent.width
        spacing: Theme.rem(0.5)
        Text {
            text: field.label
            visible: text !== ""
            color: input.activeFocus ? Theme.text : Theme.muted
            font.family: Theme.font
            font.pixelSize: Theme.smallSize
            font.weight: Font.DemiBold
        }
        Rectangle {
            id: box
            width: parent.width
            height: Theme.fieldHeight
            radius: Theme.radiusSmall
            color: Qt.rgba(0, 0, 0, 0.3)
            border.width: 1
            border.color: input.activeFocus ? Theme.accent : Theme.stroke
            Behavior on border.color { ColorAnimation { duration: 200 } }
            FocusRing { active: input.activeFocus; itemRadius: box.radius; glowSize: Theme.rem(1.4); glowAlpha: 0.35 }

            TextInput {
                id: input
                anchors.fill: parent
                anchors.leftMargin: Theme.rem(1.1)
                anchors.rightMargin: Theme.rem(1.1)
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.text
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentText
                font.family: Theme.font
                font.pixelSize: Theme.rem(1.1)
                passwordCharacter: "●"
                clip: true
                onTextEdited: field.edited()
                Keys.onReturnPressed: field.openKeyboard()
                Keys.onEnterPressed: field.openKeyboard()
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: input.text === ""
                    text: field.placeholder
                    color: Theme.faint
                    font: input.font
                }
            }
            PadHint {
                anchors.right: parent.right
                anchors.rightMargin: Theme.rem(0.8)
                anchors.verticalCenter: parent.verticalCenter
                visible: input.activeFocus && field.keyboard !== null && !field.keyboard.shown
                button: "A"
                label: qsTr("Keyboard")
                onClicked: field.openKeyboard()
            }
            MouseArea {
                anchors.fill: parent
                z: -1
                onClicked: input.forceActiveFocus()
            }
        }
        Text {
            width: parent.width
            visible: field.status !== ""
            text: field.status
            wrapMode: Text.WordWrap
            color: field.statusIsError ? Theme.danger : Theme.accent
            font.family: Theme.font
            font.pixelSize: Theme.smallSize
        }
    }
}
