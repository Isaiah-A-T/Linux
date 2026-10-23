// The game/app sheet: play, install with progress, uninstall, game settings.

import { post } from "./api.js";
import { h, icon, SOURCE_LABEL, timeAgo } from "./dom.js";
import { openGameSettings } from "./gamesettings.js";
import { confirmSheet, openSheet, toast } from "./layers.js";
import { pollJobs, state, subscribe } from "./state.js";

export async function launch(item) {
  try {
    await post("library/launch", { id: item.id });
    toast(`Starting ${item.title}`, icon("play"));
  } catch (e) {
    toast(e.message, icon("info"));
  }
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
    const actions = [];
    if (item.installed && !job) {
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
    if (item.installed && item.source !== "app") {
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
    if (item.kind === "game") {
      actions.push(h("button.btn.f.ring", {
        onclick: () => { close(); openGameSettings(item, { onBack: () => openDetails(item, { onChange }) }); },
      }, icon("sliders"), "Game settings"));
    }
    actions.push(h("button.btn.f.ring", { onclick: close }, "Close"));
    const runner = item.source === "steam" ? "Runs through Steam with Steam's Proton"
      : item.source === "app" ? "Desktop app" : "Runs with GE-Proton in its own Wine prefix";
    return [
      h("div.hero", { style: { backgroundImage: `url("${item.art?.hero || item.art?.cover || ""}")` } }),
      h("div.inner",
        h("span.pill", { class: item.source === "app" ? "flatpak" : "snap" }, SOURCE_LABEL[item.source] || item.source),
        h("h3", { style: { fontSize: "2.6rem", marginTop: "0.6rem" } }, item.title),
        h("p", {}, [timeAgo(item.last_played), runner].filter(Boolean).join(" · ")),
        h("div.actions", actions)),
    ];
  }, { cls: "detail", onClose: () => unsub?.() });
  unsub = subscribe((key) => {
    if (key !== "jobs") return;
    const running = !!jobFor(item.id);
    if (running || sheet._wasRunning) {
      if (sheet._wasRunning && !running) item.installed = true;
      sheet._wasRunning = running;
      sheet.render();
    }
  });
}
