// A Store app page: icon, description, screenshots and install.

import { get, post } from "../api.js";
import { h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { confirmSheet, toast } from "../layers.js";
import { pollJobs, setHero, state, subscribe } from "../state.js";

export function render(ctx, params) {
  const el = h("div.view", h("div.app-page", h("div.empty", h("span.spin"))));
  const page = el.firstChild;
  let app = null;

  const jobKey = () => `${app.source}:${app.id}`;
  const runningJob = () => (state.jobs || []).find((j) => j.item_id === jobKey() && j.state === "running");

  async function doInstall(source = app.source, id = app.id) {
    try {
      await post("store/install", { source, id });
      toast(`Installing ${app.title}`, icon("download"));
      pollJobs();
    } catch (e) {
      toast(e.message, icon("info"));
    }
  }

  function actions() {
    const job = runningJob();
    if (job) {
      return [h("div", { style: { width: "26rem" } },
        h("b", {}, `${Math.round(job.progress)}%`), h("small", { style: { color: "var(--muted)", marginLeft: ".6rem" } }, job.message),
        h("div.meter", h("i", { style: { width: `${job.progress}%` } })))];
    }
    if (app.installed) {
      return [
        h("button.btn.primary.f.ring", { "data-autofocus": true, onclick: () => ctx.go("library", { tab: "app" }) }, icon("grid"), "In your library"),
        h("button.btn.danger.f.ring", {
          onclick: async () => {
            if (!(await confirmSheet({ title: `Remove ${app.title}?`, ok: "Remove", danger: true }))) return;
            await post("store/remove", { source: app.source, id: app.id }).catch((e) => toast(e.message));
            pollJobs();
            load();
          },
        }, icon("trash"), "Remove"),
      ];
    }
    const out = [h("button.btn.primary.f.ring", { "data-autofocus": true, onclick: () => doInstall() }, icon("download"),
      `Install from ${app.source === "flatpak" ? "Flathub" : "Snap Store"}`)];
    for (const alt of params.also || []) {
      out.push(h("button.btn.f.ring", { onclick: () => doInstall(alt.source, alt.id) },
        `Use ${alt.source === "flatpak" ? "Flathub" : "Snap"} instead`));
    }
    return out;
  }

  function paint() {
    const keepFocus = el.querySelector(".focused") ? true : false;
    page.replaceChildren(
      h("div.app-top",
        app.icon ? h("img", { src: app.icon, alt: "" }) : h("div.ico"),
        h("div",
          h("h1", {}, app.title),
          h("div.dev", {}, [app.developer, app.summary].filter(Boolean).join(" · ")),
          h(`span.pill.${app.source}`, {}, app.source === "flatpak" ? "Flathub" : "Snap Store"))),
      h("div.app-actions", { "data-group": true }, actions()),
      app.screenshots?.length ? h("div.shots", { "data-group": true }, app.screenshots.map((s) =>
        h("div.shot.f.ring", h("img", { src: s, alt: "", loading: "lazy" })))) : null,
      h("div.desc", {}, app.description));
    if (keepFocus || !document.querySelector(".focused")?.isConnected) {
      const first = page.querySelector("[data-autofocus]") || page.querySelector(".f");
      if (first) focus(first, { scroll: false });
    }
  }

  async function load() {
    try {
      app = await get(`store/app?source=${params.source}&id=${encodeURIComponent(params.id)}`);
    } catch (e) {
      page.replaceChildren(h("div.empty", {}, e.message));
      return;
    }
    paint();
    setHero(null); // only games change the background
    ctx.ready();
  }

  let wasRunning = false;
  const unsub = subscribe((k) => {
    if (k !== "jobs" || !app) return;
    const running = !!runningJob();
    if (running || wasRunning) {
      if (wasRunning && !running) app.installed = !app.installed;
      wasRunning = running;
      paint();
    }
  });

  load();
  return { el, hints: [["A", "Select"], ["B", "Back"]], destroy: unsub };
}
