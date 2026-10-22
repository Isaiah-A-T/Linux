// Step 5: create the first profile: avatar, name and password, like
// making a profile on a new console. The username is derived from the
// name by Calamares and can be changed under "More options".
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick
import "components"

FocusScope {
    id: root
    function onActivate() { scaffold.activate() }
    function onLeave() { saveAvatar() }

    // "" is the sign-in screen's default: the name's initial on a colour
    // picked from the username (see Theme.colorFor).
    readonly property var avatars: ["", "spark", "wave", "orbit", "peak", "leaf", "bolt", "drop", "ring"]
    property int avatarIndex: 0
    property bool moreOptions: false
    readonly property string avatarDir: Qt.resolvedUrl("images/avatars/")
    readonly property string displayName: config.fullName !== "" ? config.fullName : qsTr("Player")
    readonly property color profileColor: Theme.colorFor(config.loginName !== "" ? config.loginName : "player")

    // Calamares' users module has no avatar field, so the choice is
    // written to a file that the lumen-avatar shellprocess step copies
    // into the new system. Needs QML_XHR_ALLOW_FILE_WRITE=1 (set by
    // lumen-installer).
    function saveAvatar() {
        var xhr = new XMLHttpRequest();
        xhr.open("PUT", "file:///tmp/lumen-installer/avatar");
        xhr.send(avatars[avatarIndex]);
    }

    // The sign-in screen's avatar: picture, or initial on a colour.
    component Avatar: Rectangle {
        property string picture: ""
        radius: width / 2
        color: picture === "" ? root.profileColor : Theme.glass
        Text {
            anchors.centerIn: parent
            visible: parent.picture === ""
            text: root.displayName.charAt(0).toUpperCase()
            color: Theme.accentText
            font.family: Theme.font
            font.pixelSize: parent.width * 0.42
            font.weight: Font.Black
        }
        Image {
            anchors.fill: parent
            visible: parent.picture !== ""
            source: parent.picture !== "" ? root.avatarDir + parent.picture + ".png" : ""
            sourceSize: Qt.size(256, 256)
            smooth: true
            mipmap: true
        }
    }

    PageScaffold {
        id: scaffold
        kicker: qsTr("Profile")
        title: qsTr("Create your profile")
        subtitle: qsTr("This is who you'll sign in as. You can add more people later.")
        initialFocus: avatarRow
        keyboard: osk

        aside: Item {
            width: parent.width
            height: Theme.rem(18)
            // .user.focused .avatar: gap ring, colour ring and glow
            Item {
                id: preview
                y: Theme.rem(2.2)
                x: Theme.rem(0.6)
                width: Theme.rem(9); height: width
                Repeater {
                    model: 7
                    Rectangle {
                        required property int index
                        anchors.centerIn: parent
                        width: preview.width + Theme.rem(1.1) + (index + 1) * Theme.rem(0.9)
                        height: width; radius: width / 2
                        color: Qt.rgba(root.profileColor.r, root.profileColor.g, root.profileColor.b,
                                       0.09 * Math.pow(1 - index / 7, 2))
                    }
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: preview.width + Theme.rem(1.1); height: width; radius: width / 2
                    color: root.avatars[root.avatarIndex] === "" ? root.profileColor : Theme.accent
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: preview.width + Theme.rem(0.6); height: width; radius: width / 2
                    color: Theme.bg0
                }
                Avatar { anchors.fill: parent; picture: root.avatars[root.avatarIndex] }
            }
            Column {
                anchors.left: preview.left
                anchors.top: preview.bottom
                anchors.topMargin: Theme.rem(1.6)
                spacing: Theme.rem(0.2)
                Text {
                    text: root.displayName
                    color: Theme.text
                    font.family: Theme.font
                    font.pixelSize: Theme.rem(1.6)
                    font.weight: Font.Bold
                }
                Text {
                    text: config.loginName !== "" ? "@" + config.loginName : ""
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: Theme.bodySize
                }
            }
        }

        Flickable {
            id: form
            anchors.fill: parent
            contentHeight: fields.implicitHeight + Theme.rem(2)
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // Keep the focused field on screen when moving with the d-pad.
            function reveal(item) {
                var p = item.mapToItem(fields, 0, 0);
                var pad = Theme.rem(1.5);
                if (p.y - pad < contentY) contentY = Math.max(0, p.y - pad);
                else if (p.y + item.height + pad > contentY + height)
                    contentY = Math.min(Math.max(0, contentHeight - height), p.y + item.height - height + pad);
            }

            Column {
                id: fields
                width: form.width - Theme.rem(2)
                x: Theme.rem(1)
                spacing: Theme.rem(1.3)
                topPadding: Theme.rem(1)

                Text {
                    text: qsTr("Avatar")
                    color: avatarRow.activeFocus ? Theme.text : Theme.muted
                    font.family: Theme.font
                    font.pixelSize: Theme.smallSize
                    font.weight: Font.DemiBold
                }
                ListView {
                    id: avatarRow
                    width: parent.width
                    height: Theme.rem(6)
                    orientation: ListView.Horizontal
                    spacing: Theme.rem(1)
                    leftMargin: Theme.rem(0.8)
                    clip: false
                    model: root.avatars
                    currentIndex: root.avatarIndex
                    focus: true
                    KeyNavigation.down: nameField
                    KeyNavigation.priority: KeyNavigation.AfterItem
                    onActiveFocusChanged: if (activeFocus) form.reveal(avatarRow)
                    onCurrentIndexChanged: root.avatarIndex = currentIndex
                    Keys.onReturnPressed: nameField.forceActiveFocus()
                    delegate: Item {
                        id: cell
                        required property int index
                        required property string modelData
                        property bool current: ListView.isCurrentItem
                        width: Theme.rem(4.6); height: width
                        y: Theme.rem(0.7)
                        scale: current && avatarRow.activeFocus ? 1.15 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.normal; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.ease } }
                        Avatar { anchors.fill: parent; picture: cell.modelData }
                        FocusRing { active: cell.current && avatarRow.activeFocus; itemRadius: cell.width / 2; glowSize: Theme.rem(1.6) }
                        Rectangle {
                            visible: cell.current && !avatarRow.activeFocus
                            anchors.fill: parent; anchors.margins: -Theme.rem(0.3)
                            radius: width / 2; color: "transparent"
                            border.width: Theme.ringWidth; border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5)
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { avatarRow.currentIndex = cell.index; avatarRow.forceActiveFocus() }
                        }
                    }
                }

                ConsoleField {
                    id: nameField
                    width: parent.width
                    label: qsTr("Your name")
                    placeholder: qsTr("What should we call you?")
                    keyboard: osk
                    text: config.fullName
                    onEdited: config.setFullName(text)
                    KeyNavigation.up: avatarRow
                    KeyNavigation.down: passField
                    onActiveFocusChanged: if (activeFocus) form.reveal(nameField)
                }

                ConsoleField {
                    id: passField
                    width: parent.width
                    label: qsTr("Password")
                    placeholder: config.permitWeakPasswords ? qsTr("A PIN or password") : qsTr("Choose a password")
                    echoMode: TextInput.Password
                    keyboard: osk
                    text: config.userPassword
                    onEdited: config.setUserPassword(text)
                    status: text !== "" && config.userPasswordValidity !== 0 ? config.userPasswordMessage : ""
                    statusIsError: config.userPasswordValidity === 2
                    KeyNavigation.up: nameField
                    KeyNavigation.down: confirmField
                    onActiveFocusChanged: if (activeFocus) form.reveal(passField)
                }

                ConsoleField {
                    id: confirmField
                    width: parent.width
                    label: qsTr("Confirm password")
                    placeholder: qsTr("Type it again")
                    echoMode: TextInput.Password
                    keyboard: osk
                    text: config.userPasswordSecondary
                    onEdited: config.setUserPasswordSecondary(text)
                    status: text !== "" && text !== passField.text ? qsTr("Passwords don't match yet.") : ""
                    KeyNavigation.up: passField
                    KeyNavigation.down: moreBlade
                    onActiveFocusChanged: if (activeFocus) form.reveal(confirmField)
                }

                Blade {
                    id: moreBlade
                    width: parent.width
                    height: Theme.rem(3.6)
                    glass: false
                    KeyNavigation.up: confirmField
                    KeyNavigation.down: root.moreOptions ? loginField : null
                    onActivated: root.moreOptions = !root.moreOptions
                    onActiveFocusChanged: if (activeFocus) form.reveal(moreBlade)
                    Text {
                        anchors.left: parent.left; anchors.leftMargin: Theme.rem(1.1)
                        anchors.verticalCenter: parent.verticalCenter
                        text: qsTr("More options")
                        color: Theme.text
                        font.family: Theme.font
                        font.pixelSize: Theme.bodySize
                        font.weight: Font.DemiBold
                    }
                    Text {
                        anchors.right: parent.right; anchors.rightMargin: Theme.rem(1.1)
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.moreOptions ? "−" : "+"
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: Theme.rem(1.4)
                    }
                }

                ConsoleField {
                    id: loginField
                    visible: root.moreOptions
                    width: parent.width
                    label: qsTr("Username")
                    placeholder: qsTr("lowercase, no spaces")
                    keyboard: osk
                    text: config.loginName
                    validator: RegularExpressionValidator { regularExpression: /[a-z_][a-z0-9_-]*[$]?/ }
                    onEdited: config.setLoginName(text)
                    status: config.loginNameStatus
                    KeyNavigation.up: moreBlade
                    KeyNavigation.down: hostField
                    onActiveFocusChanged: if (activeFocus) form.reveal(loginField)
                }

                ConsoleField {
                    id: hostField
                    visible: root.moreOptions
                    width: parent.width
                    label: qsTr("Console name")
                    placeholder: qsTr("How this device shows up on your network")
                    keyboard: osk
                    text: config.hostname
                    validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9][-a-zA-Z0-9_]*/ }
                    onEdited: config.setHostName(text)
                    status: config.hostnameStatus
                    KeyNavigation.up: loginField
                    onActiveFocusChanged: if (activeFocus) form.reveal(hostField)
                }

                Text {
                    width: parent.width
                    visible: config.ready
                    text: "✓  " + qsTr("Looks good. Press ☰ to continue.")
                    color: Theme.accent
                    font.family: Theme.font
                    font.pixelSize: Theme.smallSize
                    font.weight: Font.DemiBold
                }
            }
        }
    }

    OnScreenKeyboard { id: osk }
}
