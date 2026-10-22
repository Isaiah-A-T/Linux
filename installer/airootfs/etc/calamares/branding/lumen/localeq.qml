// Step 2: time zone. Region list on the left, cities on the right;
// d-pad left/right moves between them, A on a city confirms.
import io.calamares.core 1.0
import io.calamares.ui 1.0

import QtQuick
import "components"

FocusScope {
    id: root
    function onActivate() { scaffold.activate() }
    function onLeave() {}

    property string region: config.currentLocation ? config.currentLocation.region : ""
    Component.onCompleted: if (region !== "") config.regionalZonesModel.region = region

    function regionIndex() {
        for (var i = 0; i < regions.count; ++i)
            if (config.regionModel.data(config.regionModel.index(i, 0), 0x0100 /* KeyRole */) === region) return i;
        return -1;
    }

    PageScaffold {
        id: scaffold
        kicker: qsTr("Region")
        title: qsTr("Where are you?")
        subtitle: qsTr("This sets your clock and time zone.")
        initialFocus: zones.count > 0 ? zones : regions
        onEntered: { regions.playIn(); zones.playIn() }

        aside: Column {
            topPadding: Theme.rem(1.6)
            spacing: Theme.rem(0.3)
            Text {
                id: clock
                color: Theme.text
                font.family: Theme.font
                font.pixelSize: Theme.rem(3)
                font.weight: Font.Light
                function refresh() { text = Qt.formatTime(new Date(), "h:mm AP") }
                Component.onCompleted: refresh()
                Timer { interval: 10000; running: true; repeat: true; onTriggered: clock.refresh() }
            }
            Text {
                text: config.currentTimezoneName
                color: Theme.accent
                font.family: Theme.font
                font.pixelSize: Theme.bodySize
                font.weight: Font.DemiBold
            }
            Text {
                width: Theme.rem(22)
                text: qsTr("Clock shown is this computer's current time.")
                wrapMode: Text.WordWrap
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: Theme.smallSize
            }
        }

        Row {
            anchors.fill: parent
            spacing: Theme.rem(1)

            BladeList {
                id: regions
                width: parent.width * 0.42
                height: parent.height
                model: config.regionModel
                textRole: "name"
                KeyNavigation.right: zones
                onCurrentIndexChanged: if (activeFocus) preview()
                function preview() {
                    root.region = config.regionModel.data(config.regionModel.index(currentIndex, 0), 0x0100 /* KeyRole */);
                    config.regionalZonesModel.region = root.region;
                }
                onPicked: (index) => { preview(); zones.currentIndex = 0; zones.forceActiveFocus() }
                Component.onCompleted: { var i = root.regionIndex(); selectedIndex = i; currentIndex = Math.max(0, i) }
            }

            BladeList {
                id: zones
                width: parent.width * 0.58 - parent.spacing
                height: parent.height
                model: config.regionalZonesModel
                textRole: "name"
                KeyNavigation.left: regions
                selectedIndex: {
                    // Re-evaluated whenever the location or the filter changes.
                    var loc = config.currentLocation;
                    void count;
                    if (!loc) return -1;
                    for (var i = 0; i < count; ++i)
                        if (model.data(model.index(i, 0), 0x0100) === loc.zone
                            && loc.region === root.region) return i;
                    return -1;
                }
                onCountChanged: currentIndex = Math.max(0, selectedIndex)
                onPicked: (index) => {
                    var zone = model.data(model.index(index, 0), 0x0100 /* KeyRole */);
                    config.setCurrentLocation(root.region, zone);
                    regions.selectedIndex = regions.currentIndex;
                    if (ViewManager.nextEnabled) ViewManager.next();
                }
            }
        }
    }
}
