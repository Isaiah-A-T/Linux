// Bottom hint bar, like the shell's: setup-wide actions on the left,
// the step's controller hints and Back / Next on the right. Calamares
// caps this bar at 64px.
//
// QML steps handle Menu (F10) and View (F9) themselves (PageScaffold),
// so the on-screen keyboard can claim them while it is open. The disk
// page is a Qt widget page, so these application-wide shortcuts cover it.
import io.calamares.ui 1.0
import io.calamares.core 1.0

import QtQuick
import "components"

Item {
    id: nav
    height: Theme.barHeight
    implicitHeight: Theme.barHeight

    function clean(s) { return s.replace("&", "") }
    readonly property bool atEnd: ViewManager.currentStepIndex >= ViewManager.rowCount() - 1
    // Position of the "partition" step in settings.conf's first show list.
    readonly property int diskStep: 3
    readonly property bool onDiskPage: ViewManager.currentStepIndex === diskStep

    Shortcut {
        sequence: "F10"
        context: Qt.ApplicationShortcut
        enabled: nav.onDiskPage && ViewManager.nextEnabled
        onActivated: ViewManager.next()
    }
    Shortcut {
        sequence: "F9"
        context: Qt.ApplicationShortcut
        enabled: nav.onDiskPage && ViewManager.backEnabled
        onActivated: ViewManager.back()
    }

    Backdrop { anchors.fill: parent; originY: Theme.screenHeight - Theme.barHeight }

    Row {
        anchors.left: parent.left
        anchors.leftMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.rem(1.5)
        visible: ViewManager.quitVisible && !nav.atEnd
        PadHint {
            button: "⏻"
            label: nav.clean(ViewManager.quitLabel)
            opacity: ViewManager.quitEnabled ? 1 : 0.4
            onClicked: if (ViewManager.quitEnabled) ViewManager.quit()
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: Theme.gutter
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.rem(2)
        visible: ViewManager.backAndNextVisible

        PadHint {
            anchors.verticalCenter: parent.verticalCenter
            button: "A"; label: qsTr("Select")
        }
        PadHint {
            anchors.verticalCenter: parent.verticalCenter
            button: "B"; label: nav.clean(ViewManager.backLabel)
            visible: ViewManager.backEnabled
            onClicked: ViewManager.back()
        }
        ConsoleButton {
            anchors.verticalCenter: parent.verticalCenter
            implicitHeight: Theme.rem(2.8)
            primary: true
            hint: "☰"
            text: nav.clean(ViewManager.nextLabel)
            enabledState: ViewManager.nextEnabled
            activeFocusOnTab: false
            onActivated: if (ViewManager.nextEnabled) ViewManager.next()
        }
    }
}
