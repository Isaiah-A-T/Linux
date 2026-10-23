// Settings: the things you don't need every day. Wi-Fi and Bluetooth live in
// Quick Settings and game accounts in the Library; Settings links to them.

import { get, post } from "../api.js";
import { fmtBytes, h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { toast } from "../layers.js";
import { openQuickSettings } from "../quick.js";
import { pollJobs, setHero, state, subscribe } from "../state.js";

const UPDATE_JOB = "system:update";
const AUTO_JOB = "system:auto-update";

const AUTO_MODES = [
  ["install", "Install automatically"],
  ["download", "Download only"],
  ["off", "Off"],
];

function daysAgo(t) {
  if (!t) return "Never";
  const d = Math.floor((Date.now() / 1000 - t) / 86400);
  return d < 1 ? "Today" : d === 1 ? "Yesterday" : `${d} days ago`;
}

function timeAgo(t) {
  const m = Math.floor((Date.now() / 1000 - t) / 60);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  if (m < 24 * 60) return `${Math.floor(m / 60)} h ago`;
  return daysAgo(t).toLowerCase();
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

// What the last automatic run did, for the "Automatic updates" line.
function autoSummary(a) {
  if (!a || a.mode === "off") return "Off";
  if (a.running && a.state === "checking") return "Checking now";
  if (a.running && a.state === "downloading") return `Downloading ${plural(a.count, "update")}`;
  if (a.running && a.state === "installing") return `Installing ${plural(a.count, "update")}`;
  if (a.running && a.state === "waiting") return `${plural(a.count, "update")} ready · ${a.message}`;
  if (!a.time) return "Checks every few hours";
  const when = timeAgo(a.time);
  return {
    installed: `Installed ${plural(a.count, "update")} ${when}`,
    downloaded: `${plural(a.count, "update")} downloaded ${when} · ready to install`,
    current: `Up to date · checked ${when}`,
    waiting: `${plural(a.count, "update")} ready · ${a.message}`,
    failed: `Last try failed ${when}`,
    offline: `No connection ${when} · tries again later`,
    skipped: `${a.message} ${when}`,
  }[a.state] || `Checked ${when}`;
}

// Settings › System update: pacman (the OS and the Lumen shell), then Flatpak
// and Snap apps, in place. Repaints itself from the jobs poll while it runs.
function updatePage() {
  const box = h("div.update");
  let info = null;
  let checking = false;
  const job = () => [...(state.jobs || [])].reverse().find((j) => j.item_id === UPDATE_JOB);

  async function check() {
    checking = true;
    paint();
    try {
      info = await post("update/check");
    } catch (e) {
      toast(e.message, icon("info"));
    }
    checking = false;
    paint(true);
  }

  async function start() {
    try {
      await post("update/start");
      pollJobs();
    } catch (e) {
      toast(e.message, icon("info"));
    }
  }

  async function setAuto(mode) {
    if (info?.auto?.mode === mode) return;
    try {
      info = await post("update/auto", { mode });
    } catch (e) {
      toast(e.message, icon("info"));
    }
    paint();
  }

  // A restart drops a PS5 back into its own system software, so there it's
  // "turn off, then start Lumen again".
  const rebootNeeded = () => (job()?.state === "done" && job().reboot) || (!job() && info?.reboot);
  const restartText = () => (info?.ps5 ? "Turn off, then start Lumen again from your PS5" : "The new system and shell start after a restart.");

  function headline() {
    const j = job();
    const a = info?.auto;
    if (j?.state === "running") {
      return [h("b", {}, `Updating… ${Math.round(j.progress)}%`),
        h("div.meter", h("i", { style: { width: `${j.progress}%` } })),
        h("small", {}, [j.message, j.detail].filter(Boolean).join(" · "))];
    }
    if (a?.running && a.state === "installing") {
      return [h("b", {}, "Installing updates in the background…"), h("div.meter.busy", h("i")),
        h("small", {}, "Keep Lumen on until this finishes. You can keep playing.")];
    }
    if (a?.running && a.state === "downloading") {
      return [h("b", {}, `Downloading ${plural(a.count, "update")} in the background…`), h("div.meter.busy", h("i"))];
    }
    if (rebootNeeded()) return [h("b", {}, info?.ps5 ? "Turn Lumen off and on to finish updating" : "Restart to finish updating"), h("small", {}, restartText())];
    if (j?.state === "done") return [h("b", {}, "Lumen OS is up to date")];
    if (j?.state === "failed") return [h("b", {}, "The update didn't finish"), h("small", {}, j.message || j.detail || "")];
    if (checking) return [h("b", {}, "Checking for updates…")];
    if (info?.error) return [h("b", {}, "Couldn't check for updates"), h("small", {}, info.error)];
    if (!info?.checked && a?.state === "downloaded" && a.count) return [h("b", {}, `${plural(a.count, "update")} ready to install`), h("small", {}, "Already downloaded, so installing is quick.")];
    if (!info?.checked && a?.state === "current" && !a.running) return [h("b", {}, "Lumen OS is up to date")];
    if (!info?.checked) return [h("b", {}, "Check for updates or update now")];
    const n = info.packages.length + info.apps;
    if (!n) return [h("b", {}, "Lumen OS is up to date")];
    const pkgs = info.packages.slice(0, 6).map((p) => `${p.name} ${p.new}`);
    if (info.packages.length > 6) pkgs.push(`and ${info.packages.length - 6} more`);
    if (info.apps) pkgs.push(`${info.apps} app${info.apps === 1 ? "" : "s"}`);
    return [h("b", {}, `${n} update${n === 1 ? "" : "s"} available`), h("small", {}, pkgs.join(" · "))];
  }

  function paint(refocus = false) {
    const keep = box.querySelector(".focused")?.dataset.key;
    const j = job();
    const a = info?.auto;
    const running = j?.state === "running" || (a?.running && a.state === "installing");
    const live = state.info.live;
    const reboot = rebootNeeded();
    const actions = [];
    if (reboot) {
      const [action, ic, label] = info?.ps5 ? ["poweroff", "power", "Turn off now"] : ["reboot", "restart", "Restart now"];
      actions.push(h("button.btn.primary.f.ring", { "data-key": "restart", onclick: () => post("power", { action }).catch((e) => toast(e.message, icon("info"))) },
        icon(ic), label));
    }
    actions.push(
      h(`button.btn.f.ring${reboot ? "" : ".primary"}`,
        { "data-key": "start", disabled: running || live || !info?.available, onclick: start }, icon("update"), "Update now"),
      h("button.btn.f.ring", { "data-key": "check", disabled: running || checking || live || !info?.available, onclick: check },
        icon("search"), "Check for updates"));
    const modes = h("div.tabs", { "data-group": true, style: { padding: 0, flexWrap: "wrap" } },
      AUTO_MODES.map(([mode, label]) => h(`button.tab.f.ring${(a?.mode || "install") === mode ? ".sel" : ""}`,
        { "data-key": `auto-${mode}`, disabled: live || !info?.available, onclick: () => setAuto(mode) }, label)));
    box.replaceChildren(
      h("div.job", headline()),
      // Buttons right under the status so → from the nav lands on them.
      h("div.actions", { "data-group": true, style: { display: "flex", gap: "1rem", flexWrap: "wrap", margin: "1.4rem 0" } }, actions),
      h("div.kv",
        "Lumen", h("b", {}, state.info.version || ""),
        "Last updated", h("b", {}, daysAgo(info?.last_upgrade)),
        "In the background", h("b", {}, live ? "After you install Lumen OS" : autoSummary(a))),
      h("h3", { style: { margin: "1.8rem 0 .8rem" } }, "Automatic updates"),
      modes,
      h("p", { style: { color: "var(--muted)", lineHeight: 1.6, marginTop: "1rem" } },
        (a?.mode || "install") === "install"
          ? "Lumen checks for updates every few hours and installs them in the background, never while a game is running. You'll be asked to restart when a new kernel or shell needs it."
          : a.mode === "download"
            ? "Lumen downloads updates in the background. Install them here with Update now."
            : "Lumen won't look for updates by itself. Use Update now when you want them."),
      h("p", { style: { color: "var(--muted)", lineHeight: 1.6, marginTop: "1rem" } },
        live ? "Install Lumen OS to get updates. The live system resets when it restarts."
          : info && !info.available ? "The update helper isn't installed on this system."
            : "Updates the system, the Lumen shell, and your Flatpak and Snap apps without reinstalling. Your games, saves and settings stay put. Steam, Epic and GOG games update from the Library."));
    const again = keep && box.querySelector(`[data-key="${keep}"]:not(:disabled)`);
    if (again) focus(again, { scroll: false });
    else if ((refocus || keep) && box.isConnected) {
      // Both buttons are disabled while an update runs; park focus on the nav.
      const next = box.querySelector(".f:not(:disabled)") || document.querySelector(".settings .nav .sel");
      if (next) focus(next, { scroll: false });
    }
  }

  let last = "";
  let lastAuto = "";
  const unsub = subscribe((k) => {
    if (k !== "jobs" || !box.isConnected) return;
    // Background (automatic) updates show up in the jobs poll too; refetch
    // the status whenever one starts, moves on or finishes.
    const auto = (state.jobs || []).find((x) => x.item_id === AUTO_JOB);
    const autoSig = auto ? `${auto.state}:${auto.message}` : "";
    if (autoSig !== lastAuto) {
      lastAuto = autoSig;
      get("update").then((u) => { info = u; paint(); }).catch(() => {});
    }
    const j = job();
    const sig = j ? `${j.id}:${j.state}:${j.progress}:${j.message}:${j.detail}` : "";
    if (sig === last) return;
    const finished = last.includes(":running:") && j && j.state !== "running";
    last = sig;
    if (finished) get("update").then((u) => { info = u; paint(); }).catch(() => paint());
    else paint();
  });

  return {
    destroy: unsub,
    build: async () => {
      info = await get("update").catch(() => null);
      paint();
      return box;
    },
  };
}

export function render(ctx, params = {}) {
  let page = params.page || "storage";
  const update = updatePage();
  const pane = h("div.pane");
  const nav = h("div.nav", { "data-group": true });
  const el = h("div.view",
    h("div.page-head", h("h1", {}, "Settings")),
    h("div.view.settings", { style: { position: "relative", flex: "1", minHeight: "0" } }, nav, pane));

  const pages = {
    storage: ["Storage", "disk", async () => {
      const about = await get("about");
      return about.disks.map((d) => h("div", { style: { marginBottom: "1.6rem" } },
        h("b", {}, d.label), h("small", { style: { color: "var(--muted)", marginLeft: ".6rem" } }, d.path),
        h("div.meter", h("i", { style: { width: `${(100 * d.used) / d.total}%` } })),
        h("small", { style: { color: "var(--muted)" } }, `${fmtBytes(d.used)} used of ${fmtBytes(d.total)}`)));
    }],
    update: ["System update", "update", update.build],
    controllers: ["Controllers", "pad", async () => {
      const pads = [...(navigator.getGamepads?.() || [])].filter(Boolean);
      return [
        pads.length ? h("div.list", pads.map((p) => h("div.item", icon("pad"),
          h("div.grow", h("b", {}, p.id.replace(/\(.*?\)/g, "").trim() || "Controller"), h("small", {}, `Player ${p.index + 1} · ${p.mapping || "custom"} mapping`)))))
          : h("p", { style: { color: "var(--muted)" } }, "No controllers detected. Press any button on a connected controller."),
        h("p", { style: { color: "var(--muted)", lineHeight: 1.6 } }, "Pair wireless controllers from Bluetooth in Quick Settings."),
      ];
    }],
    about: ["About", "info", async () => {
      const a = await get("about");
      return [h("div.kv",
        "Lumen", h("b", {}, a.version),
        "Kernel", h("b", {}, a.kernel),
        "Device name", h("b", {}, a.hostname),
        "Signed in", h("b", {}, state.me?.name || ""))];
    }],
  };

  const links = [
    ["Wi-Fi & Bluetooth", "wifi", "Opens Quick settings", () => openQuickSettings()],
    ["Game accounts", "link", "Opens Library › Accounts", () => ctx.go("library", { tab: "accounts" })],
  ];

  async function show(key) {
    page = key;
    paintNav();
    const [title, , build] = pages[key];
    pane.replaceChildren(h("h2", {}, title), h("div.empty", h("span.spin")));
    const content = await build();
    if (page === key) pane.replaceChildren(h("h2", {}, title), ...[].concat(content));
  }

  function paintNav() {
    const keep = nav.querySelector(".focused")?.dataset.key;
    nav.replaceChildren(
      ...Object.entries(pages).map(([key, [label, ic]]) =>
        h(`button.item.f.ring${key === page ? ".sel" : ""}`, { "data-key": key, onclick: () => show(key), style: key === page ? { background: "var(--glass-hi)" } : {} },
          icon(ic), h("div.grow", h("b", {}, label)), icon("chevron"))),
      h("div.section-label", {}, "Shortcuts"),
      ...links.map(([label, ic, sub, fn]) => h("button.item.f.ring", { onclick: fn },
        icon(ic), h("div.grow", h("b", {}, label), h("small", {}, sub)))));
    const again = keep && nav.querySelector(`[data-key="${keep}"]`);
    if (again) focus(again, { scroll: false });
  }

  setHero(null);
  show(page).then(() => { focus(nav.querySelector(".f")); ctx.ready(); });
  return { el, hints: [["A", "Select"], ["B", "Back"]], destroy: update.destroy };
}
