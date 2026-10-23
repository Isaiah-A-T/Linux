// The game/app sheet: play, install with progress, uninstall.

import { post } from "./api.js";
import { h, icon, SOURCE_LABEL, timeAgo } from "./dom.js";
import { confirmSheet, openSheet, toast } from "./layers.js";
import { pollJobs, pollRunning, runningEntry, state, subscribe } from "./state.js";

export async function launch(item) {
  try {
    const res = await post("library/launch", { id: item.id });
    toast(`${res.resumed ? "Resuming" : "Starting"} ${item.title}`, icon("play"));
    for (const title of res.closed || []) toast(`Closed ${title} to make room in Quick Resume`, icon("info"));
    pollRunning();
  } catch (e) {
    toast(e.message, icon("info"));
  }
}

export async function closeRunning(item) {
  const ok = await confirmSheet({
    title: `Close ${item.title}?`,
    text: "Anything you haven't saved in the game will be lost.",
    ok: "Close game", danger: true,
  });
  if (!ok) return false;
  try {
    state.running = await post("running/close", { id: item.id });
  } catch (e) {
    toast(e.message, icon("info"));
  }
  pollRunning();
  return true;
}

// The corner badge on a tile for a game in Quick Resume or a running app.
export function runningBadge(item) {
  const r = runningEntry(item.id);
  if (!r) return null;
  return r.state === "paused"
    ? h("span.qr", icon("pause"), "Quick Resume")
    : h("span.qr.live", icon("play"), "Running");
}

export function runningText(r) {
  if (!r) return "";
  if (r.state !== "paused") return "Running";
  const m = Math.round((Date.now() / 1000 - r.paused_at) / 60);
  return `Paused ${m < 1 ? "just now" : m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`}`;
}

export async function install(item) {
  try {
    const res = await post("library/install", { id: item.id });
    toast(item.source === "steam" ? `Steam is downloading ${item.title}` : `Downloading ${item.title} with Proton`, icon("download"));
    if (res.id) pollJobs();
  } catch (e) {
    toast(e.message, icon("info"));
  }
}

export function jobFor(id) {
  return (state.jobs || []).find((j) => j.item_id === id && j.state === "running");
}

export function openDetails(item, { onChange } = {}) {
  let unsub = null;
  const sheet = openSheet(({ close }) => {
    const job = jobFor(item.id);
    const run = runningEntry(item.id);
    const actions = [];
    if (run) {
      actions.push(h("button.btn.primary.f.ring", { "data-autofocus": true, onclick: () => { close(); launch(item); } },
        icon("play"), run.state === "paused" ? "Resume" : "Switch to"));
      actions.push(h("button.btn.danger.f.ring", {
        onclick: async () => { if (await closeRunning(item)) close(); },
      }, icon("x"), item.kind === "app" ? "Close app" : "Close game"));
    } else if (item.installed && !job) {
      actions.push(h("button.btn.primary.f.ring", { "data-autofocus": true, onclick: () => { close(); launch(item); } },
        icon("play"), "Play"));
    } else if (job) {
      actions.push(h("div", { style: { flex: "1" } },
        h("b", {}, `${job.title} · ${Math.round(job.progress)}%`),
        h("div.meter", h("i", { style: { width: `${job.progress}%` } }))));
    } else {
      actions.push(h("button.btn.primary.f.ring", { "data-autofocus": true, onclick: () => install(item) },
        icon("download"), "Install"));
    }
    if (item.installed && item.source !== "app" && !run) {
      actions.push(h("button.btn.danger.f.ring", {
        onclick: async () => {
          if (!(await confirmSheet({ title: `Uninstall ${item.title}?`, text: "Saves in your cloud account are kept.", ok: "Uninstall", danger: true }))) return;
          await post("library/uninstall", { id: item.id }).catch((e) => toast(e.message));
          item.installed = false;
          onChange?.();
          close();
        },
      }, icon("trash"), "Uninstall"));
    }
    actions.push(h("button.btn.f.ring", { onclick: close }, "Close"));
    const runner = item.source === "steam" ? "Runs through Steam with Steam's Proton"
      : item.source === "app" ? "Desktop app" : "Runs with GE-Proton in its own Wine prefix";
    return [
      h("div.hero", { style: { backgroundImage: `url("${item.art?.hero || item.art?.cover || ""}")` } }),
      h("div.inner",
        h("span.pill", { class: item.source === "app" ? "flatpak" : "snap" }, SOURCE_LABEL[item.source] || item.source),
        h("h3", { style: { fontSize: "2.6rem", marginTop: "0.6rem" } }, item.title),
        h("p", {}, [run?.state === "paused" ? `In Quick Resume · ${runningText(run).toLowerCase()}` : runningText(run) || timeAgo(item.last_played), runner].filter(Boolean).join(" · ")),
        h("div.actions", actions)),
    ];
  }, { cls: "detail", onClose: () => unsub?.() });
  let lastRun = JSON.stringify(runningEntry(item.id));
  unsub = subscribe((key) => {
    if (key === "running") {
      const now = JSON.stringify(runningEntry(item.id));
      if (now !== lastRun) { lastRun = now; sheet.render(); }
      return;
    }
    if (key !== "jobs") return;
    const running = !!jobFor(item.id);
    if (running || sheet._wasRunning) {
      if (sheet._wasRunning && !running) item.installed = true;
      sheet._wasRunning = running;
      sheet.render();
    }
  });
}
