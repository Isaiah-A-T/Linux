// Step 3: keyboard layout. Most controller users can accept the default
// and move on; anyone with a keyboard can pick a layout and variant and
// try it in the test field.
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
        kicker: qsTr("Keyboard")
        title: qsTr("Pick a keyboard layout")
        subtitle: qsTr("Using only a controller? The suggested layout is fine. Press Start to continue.")
        initialFocus: layouts
        keyboard: osk
        onEntered: { layouts.playIn(); variants.playIn() }

        aside: Column {
            topPadding: Theme.rem(1.4)
            Text {
                text: config.prettyStatus
                width: Theme.rem(24)
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: Theme.smallSize
            }
        }

        Column {
            anchors.fill: parent
            spacing: Theme.rem(1)

            Row {
                width: parent.width
                height: parent.height - test.height - parent.spacing
                spacing: Theme.rem(1)

                BladeList {
                    id: layouts
                    width: parent.width * 0.56
                    height: parent.height
                    model: config.keyboardLayoutsModel
                    textRole: "label"
                    selectedIndex: model.currentIndex
                    currentIndex: model.currentIndex
                    KeyNavigation.right: variants
                    KeyNavigation.down: test
                    onPicked: (index) => { model.currentIndex = index; variants.forceActiveFocus() }
                }
                BladeList {
                    id: variants
                    width: parent.width * 0.44 - parent.spacing
                    height: parent.height
                    model: config.keyboardVariantsModel
                    textRole: "label"
                    selectedIndex: model.currentIndex
                    currentIndex: model.currentIndex
                    KeyNavigation.left: layouts
                    KeyNavigation.down: test
                    onPicked: (index) => { model.currentIndex = index; test.forceActiveFocus() }
                }
            }

            ConsoleField {
                id: test
                width: parent.width
                label: qsTr("Try your keyboard")
                placeholder: qsTr("Type here to test the layout")
                keyboard: osk
                KeyNavigation.up: layouts
            }
        }
    }

    OnScreenKeyboard { id: osk }
}
