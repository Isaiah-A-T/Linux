#!/usr/bin/env python3
"""Render the Lumen installer's QML screens to PNG without Calamares.

Calamares exposes `config`, `Branding`, `ViewManager` and `Global` to the
branding QML. This script provides stand-ins with sample data so the
screens can be previewed (and checked for QML errors) on any machine with
PySide6:

    python3 -m venv venv && venv/bin/pip install PySide6
    venv/bin/python installer/preview/preview.py out/

Each screen is laid out the way Calamares does it (status bar on top,
page in the middle, button bar at the bottom) at 1920x1080, or at the
sizes given with --screen and --window.
"""
import json
import os
import sys
import tempfile

# Optional sizes, e.g. "--screen 3840x2160 --window 1280x800" to check
# that the screens fit a window smaller than the screen (what gamescope
# does to a window it doesn't make fullscreen).
def _size_arg(flag, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        value = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        w, h = value.lower().split("x")
        return int(w), int(h)
    return default


SCREEN = _size_arg("--screen", (1920, 1080))
WINDOW = _size_arg("--window", SCREEN)

# An offscreen screen (1920x1080 by default, so Theme.rem() scales like a
# 1080p TV).
_offscreen = os.path.join(os.path.dirname(os.path.abspath(__file__)), "offscreen.json")
if SCREEN != (1920, 1080):
    with open(_offscreen) as f:
        conf = json.load(f)
    conf["screens"][0].update(width=SCREEN[0], height=SCREEN[1])
    _offscreen = os.path.join(tempfile.mkdtemp(), "offscreen.json")
    with open(_offscreen, "w") as f:
        json.dump(conf, f)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen:configfile=" + _offscreen)
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import (QAbstractListModel, QByteArray, QEnum, QModelIndex, QObject,
                            QSortFilterProxyModel, QTimer, Property, Qt, QUrl, Signal, Slot)
from PySide6.QtGui import QGuiApplication, QWindow, QStandardItem, QStandardItemModel
from PySide6.QtQml import QQmlComponent, QQmlEngine, qmlRegisterSingletonInstance
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from enum import IntEnum

HERE = os.path.dirname(os.path.abspath(__file__))
BRANDING = os.path.normpath(os.path.join(HERE, "..", "airootfs", "etc", "calamares", "branding", "lumen"))

STEPS = ["Welcome", "Location", "Keyboard", "Partitions", "Users", "Summary", "Install", "Finish"]


class Branding(QObject):
    class StringEntry(IntEnum):
        ProductName = 0
        Version = 1
        ShortVersion = 2
        VersionedName = 3
        ShortVersionedName = 4
        ShortProductName = 5
    QEnum(StringEntry)

    _strings = {0: "Lumen OS", 1: "rolling", 2: "rolling", 3: "Lumen OS", 4: "Lumen OS", 5: "Lumen"}

    @Slot(int, result=str)
    def string(self, entry):
        return self._strings.get(entry, "")


class ViewManager(QAbstractListModel):
    currentStepChanged = Signal()
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._index = 0
        self._next = "&Next"

    def rowCount(self, parent=QModelIndex()):
        return len(STEPS)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return STEPS[index.row()]
        return None

    def roleNames(self):
        return {Qt.DisplayRole: QByteArray(b"display")}

    def set_step(self, i, next_label="&Next"):
        self._index = i
        self._next = next_label
        self.currentStepChanged.emit()
        self.changed.emit()

    currentStepIndex = Property(int, lambda s: s._index, notify=currentStepChanged)
    nextEnabled = Property(bool, lambda s: True, notify=changed)
    backEnabled = Property(bool, lambda s: s._index > 0, notify=changed)
    quitEnabled = Property(bool, lambda s: True, notify=changed)
    quitVisible = Property(bool, lambda s: True, notify=changed)
    backAndNextVisible = Property(bool, lambda s: s._index < 6, notify=changed)
    nextLabel = Property(str, lambda s: s._next, notify=changed)
    backLabel = Property(str, lambda s: "&Back", notify=changed)
    quitLabel = Property(str, lambda s: "&Exit setup", notify=changed)

    @Slot()
    def next(self): pass

    @Slot()
    def back(self): pass

    @Slot()
    def quit(self): pass


class Global(QObject):
    @Slot(str, result="QVariant")
    def value(self, key): return None


def string_model(rows, roles):
    """A QStandardItemModel; rows are dicts keyed by role name."""
    m = QStandardItemModel()
    ids = {}
    for n, name in enumerate(roles):
        ids[name] = Qt.DisplayRole if n == 0 else Qt.UserRole + n - 1
    m.setItemRoleNames({v: QByteArray(k.encode()) for k, v in ids.items()})
    for r in rows:
        it = QStandardItem()
        for k, v in r.items():
            it.setData(v, ids[k])
        m.appendRow(it)
    return m


class IndexedModel(QStandardItemModel):
    """Stand-in for Calamares' keyboard models, which carry currentIndex."""
    currentIndexChanged = Signal()

    def __init__(self, labels, current=0):
        super().__init__()
        self._cur = current
        self.setItemRoleNames({Qt.DisplayRole: QByteArray(b"label")})
        for l in labels:
            self.appendRow(QStandardItem(l))

    def _set(self, v):
        self._cur = v
        self.currentIndexChanged.emit()

    currentIndex = Property(int, lambda s: s._cur, _set, notify=currentIndexChanged)


class RequirementsModel(QStandardItemModel):
    """Calamares' RequirementsModel is a list model with summary flags."""
    changed = Signal()
    satisfiedRequirements = Property(bool, lambda s: False, notify=changed)
    satisfiedMandatory = Property(bool, lambda s: True, notify=changed)


class ZoneFilter(QSortFilterProxyModel):
    regionChanged = Signal()

    def __init__(self, source):
        super().__init__()
        self._region = ""
        self.setSourceModel(source)

    def _set(self, r):
        self._region = r
        self.invalidateRowsFilter()
        self.regionChanged.emit()

    def filterAcceptsRow(self, row, parent):
        idx = self.sourceModel().index(row, 0, parent)
        return self.sourceModel().data(idx, Qt.UserRole + 1) == self._region

    region = Property(str, lambda s: s._region, _set, notify=regionChanged)


def real_zones():
    try:
        with open("/usr/share/zoneinfo/zone1970.tab") as f:
            names = [l.split("\t")[2].strip() for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        return []
    return sorted(tuple(n.split("/", 1)) for n in names if "/" in n)


def real_layouts():
    """Layout descriptions from XKB's base.lst, sorted like Calamares."""
    try:
        with open("/usr/share/X11/xkb/rules/base.lst") as f:
            lines = f.read().split("\n")
    except OSError:
        return []
    out, section = [], ""
    for l in lines:
        if l.startswith("!"):
            section = l[1:].strip()
        elif section == "layout" and l.strip():
            out.append(l.strip().split(None, 1)[1])
    return sorted(out)


def build_models():
    langs = [("American English", "American English"), ("Español", "Spanish"), ("Français", "French"),
             ("Deutsch", "German"), ("Italiano", "Italian"), ("Português (Brasil)", "Portuguese (Brazil)"),
             ("日本語", "Japanese"), ("한국어", "Korean"), ("Polski", "Polish"), ("Svenska", "Swedish"),
             ("Türkçe", "Turkish"), ("Русский", "Russian")]
    languages = string_model([{"label": a, "englishLabel": b} for a, b in langs], ["label", "englishLabel"])
    # languagesModel roles in Calamares are label/englishLabel; mirror that.
    languages.setItemRoleNames({Qt.DisplayRole: QByteArray(b"label"), Qt.UserRole: QByteArray(b"englishLabel")})
    for i, (a, b) in enumerate(langs):
        languages.item(i).setData(b, Qt.UserRole)

    regions = ["Africa", "America", "Antarctica", "Asia", "Atlantic", "Australia", "Europe", "Indian", "Pacific"]
    region_model = string_model([{"name": r, "key": r} for r in regions], ["name", "key"])
    zones = [("America", z) for z in ["Anchorage", "Chicago", "Denver", "Los_Angeles", "Mexico_City",
                                       "New_York", "Phoenix", "Puerto_Rico", "Sao_Paulo", "Toronto", "Vancouver"]]
    zones += [("Europe", z) for z in ["Amsterdam", "Berlin", "London", "Madrid", "Paris", "Rome"]]
    # Real lists are much longer than the sample (America alone has over a
    # hundred zones, and the preselected rows sit far down), which is what
    # long-list bugs need; use the system's tz and XKB data when present.
    zones = real_zones() or zones
    zone_model = string_model([{"name": z.replace("_", " "), "key": z, "region": r} for r, z in zones],
                              ["name", "key", "region"])
    regional = ZoneFilter(zone_model)
    regional.region = "America"

    layouts = IndexedModel(["English (US)", "English (UK)", "French", "German", "Japanese", "Portuguese (Brazil)",
                            "Spanish", "Spanish (Latin American)", "Swedish"], 0)
    xkb = real_layouts()
    if xkb:
        layouts = IndexedModel(xkb, xkb.index("English (US)") if "English (US)" in xkb else 0)
    variants = IndexedModel(["Default", "English (US, intl., with dead keys)", "English (Colemak)",
                             "English (Dvorak)", "English (Macintosh)"], 0)

    requirements = RequirementsModel()
    requirements.setItemRoleNames({Qt.DisplayRole: QByteArray(b"name"), Qt.UserRole: QByteArray(b"negatedText"),
                                   Qt.UserRole + 1: QByteArray(b"satisfied"), Qt.UserRole + 2: QByteArray(b"mandatory")})
    for name, text, ok, mandatory in [
            ("storage", "", True, True),
            ("internet", "Not connected to the Internet. That's fine: Lumen installs offline.", False, False)]:
        it = QStandardItem(name)
        it.setData(text, Qt.UserRole); it.setData(ok, Qt.UserRole + 1); it.setData(mandatory, Qt.UserRole + 2)
        requirements.appendRow(it)

    summary = string_model([
        {"title": "Location", "message": "The system language will be set to English (United States).<br/>Time zone: America/New York."},
        {"title": "Keyboard", "message": "Keyboard layout: English (US), Default."},
        {"title": "Partitions", "message": "<b>Erase</b> disk <b>Samsung SSD 980 (1 TB)</b> and install Lumen OS.<br/>"
                                           "Create new <b>1 TB</b> partition table, ext4 root, 300 MiB EFI system partition."},
        {"title": "Users", "message": "Create user <b>alex</b> (Alex) in groups wheel, video, input, audio."},
    ], ["title", "message"])

    return dict(languages=languages, regions=region_model, regional=regional, layouts=layouts,
                variants=variants, requirements=requirements, summary=summary)


CONFIGS = {
    "welcomeq": """
        QtObject {
            property var languagesModel: m_languages
            property int localeIndex: 0
            property var requirementsModel: m_requirements
        }""",
    "localeq": """
        QtObject {
            property var regionModel: m_regions
            property var regionalZonesModel: m_regional
            property var currentLocation: QtObject { property string region: "America"; property string zone: "New_York" }
            property string currentTimezoneName: "America/New York"
            function setCurrentLocation(r, z) { currentLocation.region = r; currentLocation.zone = z }
        }""",
    "keyboardq": """
        QtObject {
            property var keyboardLayoutsModel: m_layouts
            property var keyboardVariantsModel: m_variants
            property string prettyStatus: "Set keyboard model to <b>Generic 105-key PC</b>, layout <b>English (US)</b>."
        }""",
    "usersq": """
        QtObject {
            property string fullName: "Alex"
            property string loginName: "alex"
            property string hostname: "lumen-ryzen"
            property string userPassword: "1234"
            property string userPasswordSecondary: "1234"
            property int userPasswordValidity: 0
            property string userPasswordMessage: ""
            property string loginNameStatus: ""
            property string hostnameStatus: ""
            property bool permitWeakPasswords: true
            property bool ready: true
            function setFullName(t) { fullName = t } function setLoginName(t) { loginName = t }
            function setHostName(t) { hostname = t } function setUserPassword(t) { userPassword = t }
            function setUserPasswordSecondary(t) { userPasswordSecondary = t }
        }""",
    "summaryq": """
        QtObject { property var summaryModel: m_summary; property string message: "" }""",
    "finishedq": """
        QtObject {
            property bool failed: false
            property string failureMessage: ""
            property string failureDetails: ""
            function doRestart(b) {}
        }""",
    "show": "QtObject {}",
}

START = os.path.normpath(os.path.join(HERE, "..", "airootfs", "usr", "share", "lumen-installer", "start.qml"))

# (output name, page file, step index, next label, keys to send after load)
# "start" is the live ISO's power-on screen, a standalone window.
SHOTS = [
    ("00-power-on", "start", 0, "", []),
    ("01-choose", "start", 0, "", [Qt.Key_Return]),
    ("02-language", "welcomeq", 0, "&Next", []),
    ("03-region", "localeq", 1, "&Next", []),
    ("04-keyboard", "keyboardq", 2, "&Next", []),
    ("05-profile", "usersq", 4, "&Next", []),
    ("06-profile-keyboard", "usersq", 4, "&Next", [Qt.Key_Down, Qt.Key_Return, Qt.Key_Right, Qt.Key_Right]),
    ("07-summary", "summaryq", 5, "&Install", []),
    ("08-installing", "show", 6, "&Next", []),
    ("09-done", "finishedq", 7, "&Done", []),
]

SHELL = """
import QtQuick
import QtQuick.Window
Window {
    width: %(w)d; height: %(h)d; visible: true; color: "#07090d"
    property alias page: pageLoader.item
    Loader { id: top; anchors { left: parent.left; right: parent.right; top: parent.top }
             height: %(bars)s ? 64 : 0; active: %(bars)s; source: "%(branding)s/calamares-sidebar.qml" }
    Loader { id: pageLoader; anchors { left: parent.left; right: parent.right; top: top.bottom; bottom: bottom.top }
             anchors.bottomMargin: %(bars)s ? 0 : 80
             source: "%(branding)s/%(page)s.qml"; focus: true
             onLoaded: { if (item.onActivate) item.onActivate() } }
    // Calamares' own progress bar and status line under the slideshow,
    // drawn here the way stylesheet.qss styles them.
    Column {
        visible: !%(bars)s
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; bottomMargin: 24 }
        spacing: 12
        Rectangle { x: 72; width: parent.width - 144; height: 12; radius: 6; color: "#161b23"
            Rectangle { width: parent.width * 0.42; height: 12; radius: 6
                gradient: Gradient { orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#13a872" } GradientStop { position: 1; color: "#3ee6a0" } } } }
        Text { x: 72; text: "Copying files to the new system…"; color: "#9aa6b5"; font.family: "Inter"; font.pixelSize: 15 }
    }
    Loader { id: bottom; anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
             height: %(bars)s ? 64 : 0; active: %(bars)s; source: "%(branding)s/calamares-navigation.qml" }
}
"""


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
    os.makedirs(out, exist_ok=True)
    app = QGuiApplication(sys.argv)
    vm = ViewManager()
    branding = Branding()
    glob = Global()
    qmlRegisterSingletonInstance(Branding, "io.calamares.ui", 1, 0, "Branding", branding)
    qmlRegisterSingletonInstance(ViewManager, "io.calamares.ui", 1, 0, "ViewManager", vm)
    qmlRegisterSingletonInstance(Global, "io.calamares.core", 1, 0, "Global", glob)
    models = build_models()

    # Singleton instances may only be used from one engine, so every
    # screen shares this one and just swaps the `config` stand-in.
    engine = QQmlEngine()
    ctx = engine.rootContext()
    for k, m in models.items():
        ctx.setContextProperty("m_" + k, m)

    failures = 0
    for name, page, step, next_label, keys in SHOTS:
        vm.set_step(step, next_label)
        engine.clearComponentCache()
        cfg_comp = QQmlComponent(engine)
        cfg_comp.setData(("import QtQuick\n" + CONFIGS.get(page, "QtObject {}")).encode(), QUrl())
        cfg = cfg_comp.create()
        if cfg is None:
            print(name, "config error:", cfg_comp.errorString()); failures += 1; continue
        ctx.setContextProperty("config", cfg)
        # The install slideshow sits above Calamares' own progress widgets
        # and has no QML bars; the finished page keeps them.
        bars = "false" if page == "show" else "true"
        comp = QQmlComponent(engine)
        if page == "start":
            comp.loadUrl(QUrl.fromLocalFile(START))
        else:
            comp.setData((SHELL % {"branding": QUrl.fromLocalFile(BRANDING).toString(), "page": page,
                                   "bars": bars, "w": WINDOW[0], "h": WINDOW[1]}).encode(),
                         QUrl.fromLocalFile(os.path.join(HERE, "shell.qml")))
        win = comp.create()
        if win is None:
            print(name, "error:", comp.errorString()); failures += 1; continue
        if page == "start":
            # It asks for fullscreen; the offscreen platform makes that 800x800.
            win.setVisibility(QWindow.Windowed)
            win.resize(*WINDOW)
        wait(app, 900)
        for key in keys:
            QTest.keyClick(win, key)
            wait(app, 250)
        wait(app, 900)
        img = win.grabWindow()
        path = os.path.join(out, name + ".png")
        img.save(path)
        print("wrote", path)
        win.close()
        win.deleteLater()
        wait(app, 50)
    return 1 if failures else 0


def wait(app, ms):
    QTest.qWait(ms)


if __name__ == "__main__":
    sys.exit(main())
