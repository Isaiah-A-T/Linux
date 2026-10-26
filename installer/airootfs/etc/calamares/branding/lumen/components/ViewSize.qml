// Tells Theme the size of the window this QML is drawn in, so rem()
// fits the window rather than the screen. Under gamescope the window
// need not cover the screen (gamescope stretches it to fit instead), and
// sizing by the screen then made everything too big for the window.
// Calamares gives each page and bar its own QML engine, and so its own
// Theme: every root item needs one of these.
import QtQuick
import QtQuick.Window

Item {
    id: sizer
    // Window height this view doesn't see, such as Calamares' two bars
    // around a page.
    property real extraHeight: 0
    // The 64px bars can't tell the window's height; they size by width.
    property bool useHeight: true

    Binding { target: Theme; property: "viewWidth"; value: sizer.Window.width; when: sizer.Window.width > 0 }
    Binding {
        target: Theme; property: "viewHeight"
        value: sizer.Window.height + sizer.extraHeight
        when: sizer.useHeight && sizer.Window.height > 0
    }
}
