// Step 1: language. On the live ISO the power-on "Press A" screen comes
// first (usr/share/lumen-installer/start.qml); this page is what the
// installer opens on.
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
        kicker: qsTr("Language")
        title: qsTr("Choose your language")
        subtitle: qsTr("You can change this later in Settings.")
        initialFocus: languages
        onEntered: languages.playIn()

        aside: Column {
            width: parent.width
            spacing: Theme.rem(0.6)
            topPadding: Theme.rem(1.2)
            visible: !config.requirementsModel.satisfiedRequirements
            Repeater {
                model: config.requirementsModel
                Rectangle {
                    required property string negatedText
                    required property bool satisfied
                    required property bool mandatory
                    visible: !satisfied
                    width: parent.width
                    height: visible ? warn.implicitHeight + Theme.rem(1.6) : 0
                    radius: Theme.radiusSmall
                    color: Theme.glass
                    border.color: mandatory ? Theme.danger : Qt.rgba(1, 0.71, 0.28, 0.5)
                    Text {
                        id: warn
                        anchors.fill: parent
                        anchors.margins: Theme.rem(0.8)
                        wrapMode: Text.WordWrap
                        verticalAlignment: Text.AlignVCenter
                        text: (mandatory ? "✖  " : "⚠  ") + negatedText
                        color: mandatory ? Theme.danger : Theme.warning
                        font.family: Theme.font
                        font.pixelSize: Theme.smallSize
                    }
                }
            }
        }

        BladeList {
            id: languages
            anchors.fill: parent
            focus: true
            model: config.languagesModel
            textRole: "label"
            detailRole: "englishLabel"
            selectedIndex: config.localeIndex
            currentIndex: config.localeIndex
            onPicked: (index) => {
                config.localeIndex = index;
                if (ViewManager.nextEnabled) ViewManager.next();
            }
        }
    }
}
