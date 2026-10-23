// Settings: the things you don't need every day. Wi-Fi and Bluetooth live in
// Quick Settings and game accounts in the Library; Settings links to them.

import { get, post } from "../api.js";
import { fmtBytes, h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { toast } from "../layers.js";
import { openQuickSettings } from "../quick.js";
import { pollJobs, setHero, state, subscribe } from "../state.js";

const UPDATE_JOB = "system:update";

function daysAgo(t) {
  if (!t) return "Never";
  const d = Math.floor((Date.now() / 1000 - t) / 86400);
  return d < 1 ? "Today" : d === 1 ? "Yesterday" : `${d} days ago`;
}

function since(t) {
  const s = Date.now() / 1000 - t;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return daysAgo(t).toLowerCase();
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

  function headline() {
    const j = job();
    if (j?.state === "running") {
      return [h("b", {}, `Updating… ${Math.round(j.progress)}%`),
        h("div.meter", h("i", { style: { width: `${j.progress}%` } })),
        h("small", {}, [j.message, j.detail].filter(Boolean).join(" · "))];
    }
    if (j?.state === "done" && j.reboot) return [h("b", {}, "Restart to finish updating"), h("small", {}, "The new system and shell start after a restart.")];
    if (j?.state === "done") return [h("b", {}, "Lumen OS is up to date")];
    if (j?.state === "failed") return [h("b", {}, "The update didn't finish"), h("small", {}, j.message || j.detail || "")];
    if (checking) return [h("b", {}, "Checking for updates…")];
    if (info?.error) return [h("b", {}, "Couldn't check for updates"), h("small", {}, info.error)];
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
    const running = j?.state === "running";
    const live = state.info.live;
    const actions = [];
    if (j?.state === "done" && j.reboot) {
      actions.push(h("button.btn.primary.f.ring", { "data-key": "restart", onclick: () => post("power", { action: "reboot" }) },
        icon("restart"), "Restart now"));
    }
    actions.push(
      h(`button.btn.f.ring${j?.reboot && j.state === "done" ? "" : ".primary"}`,
        { "data-key": "start", disabled: running || live || !info?.available, onclick: start }, icon("update"), "Update now"),
      h("button.btn.f.ring", { "data-key": "check", disabled: running || checking || live || !info?.available, onclick: check },
        icon("search"), "Check for updates"));
    box.replaceChildren(
      h("div.job", headline()),
      // Buttons right under the status so → from the nav lands on them.
      h("div.actions", { "data-group": true, style: { display: "flex", gap: "1rem", flexWrap: "wrap", margin: "1.4rem 0" } }, actions),
      h("div.kv",
        "Lumen", h("b", {}, state.info.version || ""),
        "Last updated", h("b", {}, daysAgo(info?.last_upgrade))),
      h("p", { style: { color: "var(--muted)", lineHeight: 1.6, marginTop: "1.6rem" } },
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
  const unsub = subscribe((k) => {
    if (k !== "jobs" || !box.isConnected) return;
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

// Settings › Saves & captures: cloud saves for Epic and GOG (Steam syncs its
// own), and the controller's screenshot and clip buttons.
function savesPage() {
  const box = h("div");
  let saves = null;
  let cap = null;
  const syncJob = () => [...(state.jobs || [])].reverse().find((j) => j.item_id === "saves:all");

  const toggle = (key, label, sub, on, onclick) => h("button.item.f.ring", { "data-key": key, onclick },
    h("div.grow", h("b", {}, label), h("small", {}, sub)),
    h("span", { class: "btn" + (on ? " primary" : ""), style: { height: "2.2rem", padding: "0 1rem" } }, on ? "On" : "Off"));

  async function act(fn) {
    try {
      await fn();
    } catch (e) {
      toast(e.message, icon("info"));
    }
    paint();
  }

  function paint() {
    const keep = box.querySelector(".focused")?.dataset.key;
    const j = syncJob();
    const syncing = j?.state === "running";
    const muted = { color: "var(--muted)", lineHeight: 1.6 };
    box.replaceChildren(
      h("div.section-label", {}, "Cloud saves"),
      h("div.list", { "data-group": true },
        toggle("saves", "Cloud saves", saves.enabled ? "Synced before and after every game" : "Saves stay on this console only",
          saves.enabled, () => act(async () => { saves = await post("saves", { enabled: !saves.enabled }); })),
        h("button.item.f.ring", { "data-key": "sync", disabled: syncing || !saves.enabled,
          onclick: () => act(async () => { await post("saves/sync"); pollJobs(); }) },
          icon("update"),
          h("div.grow", h("b", {}, syncing ? `Syncing… ${Math.round(j.progress)}%` : "Sync now"),
            h("small", {}, j && !syncing ? j.message : saves.last_sync ? `Last synced ${since(saves.last_sync)}` : "Not synced yet")))),
      h("div.kv", { style: { margin: "1rem 0 0.4rem" } },
        ...saves.stores.flatMap((st) => [st.name, h("b", {}, st.connected ? st.how : "Not connected")])),
      h("div.section-label", { style: { marginTop: "2rem" } }, "Screenshots and clips"),
      h("div.kv", { style: { marginBottom: "1rem" } },
        "Screenshot", h("b", {}, "Guide + RB, or tap Share"),
        "Save a clip", h("b", {}, `Guide + LB, or hold Share · last ${cap.clip_length} seconds`)),
      h("div.list", { "data-group": true },
        toggle("clips", "Record clips in the background",
          !cap.clips_available ? "gpu-screen-recorder isn't installed" : cap.recording ? "Recording · uses a little GPU power" : cap.clips ? "Starting…" : "Off",
          cap.clips, () => act(async () => { cap = await post("capture", { clips: !cap.clips }); })),
        h("button.item.f.ring", { "data-key": "length",
          onclick: () => act(async () => {
            const all = cap.clip_lengths;
            cap = await post("capture", { clip_length: all[(all.indexOf(cap.clip_length) + 1) % all.length] });
          }) },
          h("div.grow", h("b", {}, "Clip length"), h("small", {}, "How much a saved clip goes back")),
          h("span.btn", { style: { height: "2.2rem", padding: "0 1rem" } }, `${cap.clip_length} s`))),
      h("p", { style: { ...muted, marginTop: "1.2rem" } },
        "Screenshots and clips show up in Album on the top bar. They're saved to Pictures › Screenshots and Videos › Clips."));
    const again = keep && box.querySelector(`[data-key="${keep}"]:not(:disabled)`);
    if (again) focus(again, { scroll: false });
  }

  let last = "";
  const unsub = subscribe((k) => {
    if (k !== "jobs" || !box.isConnected || !saves) return;
    const j = syncJob();
    const sig = j ? `${j.id}:${j.state}:${j.progress}` : "";
    if (sig === last) return;
    const finished = last.includes(":running:") && j && j.state !== "running";
    last = sig;
    if (finished) get("saves").then((r) => { saves = r; paint(); });
    else paint();
  });

  return {
    destroy: unsub,
    build: async () => {
      [saves, cap] = await Promise.all([get("saves"), get("capture")]);
      paint();
      return box;
    },
  };
}

export function render(ctx, params = {}) {
  let page = params.page || "storage";
  const update = updatePage();
  const savesCaptures = savesPage();
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
    saves: ["Saves & captures", "image", savesCaptures.build],
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
  return { el, hints: [["A", "Select"], ["B", "Back"]], destroy: () => { update.destroy(); savesCaptures.destroy(); } };
}
