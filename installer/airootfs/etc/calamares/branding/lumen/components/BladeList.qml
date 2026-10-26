// Vertical list navigated with the d-pad / arrow keys, styled like the
// shell's .list/.item rows. A (Return) on a row emits picked(index); the
// current choice shows an accent check. Call playIn() when the page
// appears for the shell's staggered list entrance.
import QtQuick

ListView {
    id: list
    property string textRole: "label"
    property string detailRole: ""
    property int selectedIndex: -1
    property real rowHeight: Theme.rem(4.1)
    property real reveal: 1000
    property int revealBase: 0
    signal picked(int index)

    // Rows fade and rise in one after another (45ms apart), counted from
    // the first row on screen. The start row is only known once the list
    // has scrolled to the current row (a time zone or layout far down a
    // long list), so it is picked after that scroll.
    function playIn() {
        reveal = 0;
        Qt.callLater(startReveal_);
    }
    function startReveal_() {
        // A current row far down a long list opens in the middle, with
        // its neighbours around it.
        if (currentIndex > 0 && currentIndex < count - 1) positionViewAtIndex(currentIndex, ListView.Center);
        else reveal_();
        revealBase = Math.max(0, indexAt(width / 2, contentY + Theme.rem(1.5)));
        revealAnim.restart();
    }
    NumberAnimation {
        id: revealAnim
        target: list; property: "reveal"
        from: 0; to: 14; duration: 14 * 45
        // Only the first screenful animates; every row must end up
        // visible, including ones scrolled to or loaded later.
        onFinished: list.reveal = 1000
    }

    clip: true
    spacing: Theme.rem(0.5)
    keyNavigationWraps: false
    // Let the list move first; KeyNavigation.* only fires at its edges.
    KeyNavigation.priority: KeyNavigation.AfterItem
    boundsBehavior: Flickable.StopAtBounds
    // Room for the focus ring and its glow.
    topMargin: Theme.rem(1); bottomMargin: Theme.rem(1)
    leftMargin: Theme.rem(0.8); rightMargin: Theme.rem(0.8)
    highlightFollowsCurrentItem: false
    function reveal_() {
        // positionViewAt*() ignore top/bottomMargin, which leaves the focus
        // ring of the first and last rows clipped, so pin the ends by hand.
        if (currentIndex <= 0) contentY = originY - topMargin;
        else if (currentIndex >= count - 1) contentY = Math.max(originY - topMargin, contentHeight + originY + bottomMargin - height);
        else positionViewAtIndex(currentIndex, ListView.Contain);
    }
    // Deferred so it runs after ListView's own margin-unaware scrolling.
    onCurrentIndexChanged: Qt.callLater(reveal_)
    // Models arrive before layout; place the initial row once sized.
    onHeightChanged: Qt.callLater(reveal_)
    onCountChanged: Qt.callLater(reveal_)

    delegate: Blade {
        id: row
        required property int index
        required property var model
        property string label: list.textRole !== "" && model[list.textRole] !== undefined
                               ? String(model[list.textRole]) : String(model.modelData)
        property string detail: list.detailRole !== "" && model[list.detailRole] !== undefined
                                ? String(model[list.detailRole]) : ""
        readonly property real enter: Math.max(0, Math.min(1, list.reveal - Math.max(0, index - list.revealBase)))
        width: list.width - list.leftMargin - list.rightMargin
        height: list.rowHeight
        glass: false
        highlighted: list.activeFocus && ListView.isCurrentItem
        selected: index === list.selectedIndex
        opacity: enter
        transform: Translate { y: (1 - row.enter) * Theme.rem(1.2) }
        onActivated: { list.currentIndex = index; list.forceActiveFocus(); list.picked(index) }

        Column {
            anchors.left: parent.left
            anchors.leftMargin: Theme.rem(1.1)
            anchors.right: tag.left
            anchors.rightMargin: Theme.rem(1)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.rem(0.15)
            Text {
                width: parent.width
                text: row.label
                elide: Text.ElideRight
                color: Theme.text
                font.family: Theme.font
                font.pixelSize: Theme.bodySize
                font.weight: Font.DemiBold
            }
            Text {
                visible: text !== "" && text !== row.label
                width: parent.width
                text: row.detail
                elide: Text.ElideRight
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: Theme.rem(0.88)
            }
        }
        Row {
            id: tag
            anchors.right: parent.right
            anchors.rightMargin: Theme.rem(1.1)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.rem(0.5)
            visible: row.selected
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("Selected")
                color: Theme.accent
                font.family: Theme.font
                font.pixelSize: Theme.rem(0.8)
                font.weight: Font.Bold
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "✓"
                color: Theme.accent
                font.pixelSize: Theme.rem(1.1)
                font.bold: true
            }
        }
    }

    Keys.onReturnPressed: picked(currentIndex)
    Keys.onEnterPressed: picked(currentIndex)
    // Triggers arrive as Page Up / Page Down: jump a screenful.
    Keys.onPressed: (event) => {
        var page = Math.max(1, Math.floor(height / (rowHeight + spacing)) - 1);
        if (event.key === Qt.Key_PageDown) {
            currentIndex = Math.min(count - 1, currentIndex + page); event.accepted = true;
        } else if (event.key === Qt.Key_PageUp) {
            currentIndex = Math.max(0, currentIndex - page); event.accepted = true;
        }
    }
}
