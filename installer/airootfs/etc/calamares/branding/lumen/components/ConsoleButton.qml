// The shell's .btn: a full pill, 3.2rem tall, bold label. "primary"
// fills it with the accent colour. An optional glyph shows which
// controller button triggers it.
import QtQuick

Blade {
    id: button
    property string text: ""
    property bool primary: false
    property string hint: ""
    property bool enabledState: true

    implicitWidth: row.implicitWidth + Theme.rem(3.2)
    implicitHeight: Theme.buttonHeight
    radius: height / 2
    glass: false
    focusScale: 1.04
    opacity: enabledState ? 1 : 0.4
    color: primary ? Theme.accent : Theme.glassHi
    border.width: primary ? 0 : 1
    border.color: Theme.stroke

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.rem(0.6)
        Rectangle {
            visible: button.hint !== ""
            anchors.verticalCenter: parent.verticalCenter
            width: Theme.rem(1.5); height: width; radius: width / 2
            color: button.primary ? Theme.accentText : Theme.glyph
            Text {
                anchors.centerIn: parent
                text: button.hint
                font.family: Theme.font; font.pixelSize: Theme.rem(0.72); font.weight: Font.ExtraBold
                color: button.primary ? Theme.accent : Theme.glyphText
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: button.text
            font.family: Theme.font
            font.pixelSize: Theme.bodySize
            font.weight: Font.Bold
            color: button.primary ? Theme.accentText : Theme.text
        }
    }
}
