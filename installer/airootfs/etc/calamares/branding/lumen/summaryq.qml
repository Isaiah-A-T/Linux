// Step 6: review before anything is written to disk.
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick
import "components"

FocusScope {
    id: root
    function onActivate() { scaffold.activate() }
    function onLeave() {}

    PageScaffold {
        id: scaffold
        kicker: qsTr("Ready")
        title: qsTr("Ready to set up %1").arg(Branding.string(Branding.ShortProductName))
        subtitle: qsTr("Check the details below. Nothing on this console changes until you choose Install.")
        initialFocus: list
        onEntered: { list.reveal = 0; revealAnim.restart() }

        ListView {
            id: list
            property real reveal: 1000
            NumberAnimation { id: revealAnim; target: list; property: "reveal"; from: 0; to: 8; duration: 8 * 60 }
            anchors.fill: parent
            clip: true
            spacing: Theme.rem(0.7)
            focus: true
            model: config.summaryModel
            boundsBehavior: Flickable.StopAtBounds
            topMargin: Theme.rem(1); bottomMargin: Theme.rem(1)
            leftMargin: Theme.rem(0.8); rightMargin: Theme.rem(0.8)
            delegate: Blade {
                id: card
                required property int index
                required property string title
                required property string message
                readonly property real enter: Math.max(0, Math.min(1, list.reveal - index))
                width: list.width - list.leftMargin - list.rightMargin
                height: body.implicitHeight + head.implicitHeight + Theme.rem(2.6)
                glass: false
                color: Theme.glassHi
                highlighted: list.activeFocus && ListView.isCurrentItem
                opacity: enter
                transform: Translate { y: (1 - card.enter) * Theme.rem(1.2) }
                Column {
                    anchors.fill: parent
                    anchors.margins: Theme.rem(1.1)
                    spacing: Theme.rem(0.4)
                    Text {
                        id: head
                        text: card.title.toUpperCase()
                        color: Theme.accent
                        font.family: Theme.font
                        font.pixelSize: Theme.rem(0.8)
                        font.weight: Font.Bold
                        font.letterSpacing: Theme.rem(0.8) * 0.14
                    }
                    Text {
                        id: body
                        width: parent.width
                        text: card.message
                        textFormat: Text.RichText
                        wrapMode: Text.WordWrap
                        color: Theme.text
                        font.family: Theme.font
                        font.pixelSize: Theme.bodySize
                        lineHeight: 1.3
                    }
                }
            }
        }
    }
}
