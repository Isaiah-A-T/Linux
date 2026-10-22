// Hint-bar entry: a light round controller glyph and a muted label,
// e.g. (A) Select. Wide glyphs (LB, RB) become rounded pills.
import QtQuick

Item {
    id: hint
    property string button: "A"
    property string label: ""
    readonly property bool wide: button.length > 1
    signal clicked()
    implicitWidth: row.implicitWidth
    implicitHeight: Math.max(row.implicitHeight, Theme.rem(1.7))

    Row {
        id: row
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.rem(0.55)
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: hint.wide ? glyph.implicitWidth + Theme.rem(1) : Theme.rem(1.7)
            height: Theme.rem(1.7)
            radius: hint.wide ? Theme.rem(0.5) : height / 2
            color: Theme.glyph
            Text {
                id: glyph
                anchors.centerIn: parent
                text: hint.button
                color: Theme.glyphText
                font.family: Theme.font
                font.pixelSize: Theme.rem(0.8)
                font.weight: Font.ExtraBold
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: hint.label
            color: hintMouse.containsMouse ? Theme.text : Theme.muted
            font.family: Theme.font
            font.pixelSize: Theme.rem(0.95)
        }
    }
    MouseArea {
        id: hintMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: hint.clicked()
    }
}
