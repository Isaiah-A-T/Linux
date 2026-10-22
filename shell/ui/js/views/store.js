// The Lumen Store: Flathub and Snap apps in one catalogue.

import { get } from "../api.js";
import { h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { lastDevice } from "../input.js";
import { openKeyboard } from "../osk.js";
import { setHero } from "../state.js";

export function appCard(app, ctx) {
  return h("button.app-card.f.ring", { onclick: () => ctx.go("app", { source: app.source, id: app.id, also: app.also }) },
    app.icon ? h("img", { src: app.icon, alt: "", loading: "lazy" }) : h("div.ico"),
    h("div.grow",
      h("b", {}, app.title),
      h("small", {}, app.summary),
      h(`span.pill.${app.source}`, {}, app.source === "flatpak" ? "Flathub" : "Snap"),
      app.also?.length ? h("span.pill", { style: { marginLeft: ".4rem", color: "var(--muted)" } }, "+ Snap") : null));
}

export function render(ctx, params = {}) {
  let tab = params.search ? "search" : "discover";
  let query = params.q || "";
  const tabsEl = h("div.tabs");
  const body = h("div.store-body");
  const el = h("div.view",
    h("div.page-head", h("h1", {}, "Store"), h("div.sub", {}, "Apps from Flathub and the Snap Store")),
    tabsEl, body);

  const field = h("input.field.f.ring", { placeholder: "Search apps", value: query });
  let timer;
  field.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => search(field.value), 350);
  });
  field._onSubmit = () => search(field.value, true);

  function paintTabs() {
    tabsEl.replaceChildren(
      h("span.glyph.wide", {}, "LB"),
      h(`button.tab.f${tab === "discover" ? ".sel" : ""}`, { onclick: () => setTab("discover") }, "Discover"),
      h(`button.tab.f${tab === "search" ? ".sel" : ""}`, { onclick: () => setTab("search") }, icon("search"), "Search"),
      h("span.glyph.wide", {}, "RB"));
  }

  async function discover() {
    body.replaceChildren(h("div.empty", h("span.spin")));
    const { sections } = await get("store/featured").catch(() => ({ sections: [] }));
    if (tab !== "discover") return;
    body.replaceChildren(...sections.map((s) => h("div.shelf",
      h("h2", {}, s.title),
      h("div.row", { "data-group": true }, s.apps.map((a) => appCard(a, ctx))))));
    if (!sections.length) body.replaceChildren(h("div.empty", {}, "Couldn't reach Flathub or the Snap Store. Check your connection in Quick settings."));
    const first = body.querySelector(".f");
    if (first) focus(first);
  }

  const results = h("div.search-grid", { "data-group": true });
  async function search(q, focusResults = false) {
    query = q;
    if (!q.trim()) {
      results.replaceChildren();
      return;
    }
    results.replaceChildren(h("div.empty", h("span.spin")));
    const { apps } = await get(`store/search?q=${encodeURIComponent(q)}`).catch(() => ({ apps: [] }));
    if (q !== query) return;
    results.replaceChildren(...(apps.length ? apps.map((a) => appCard(a, ctx)) : [h("div.empty", {}, `No apps found for "${q}".`)]));
    if (focusResults && results.querySelector(".f")) focus(results.querySelector(".f"));
  }

  function setTab(t) {
    tab = t;
    paintTabs();
    if (t === "discover") discover();
    else {
      body.replaceChildren(h("div.search-bar", field), results);
      focus(field);
      if (query) search(query);
      if (lastDevice === "gamepad") openKeyboard(field, { onDone: (v) => search(v, true) });
    }
  }

  paintTabs();
  setHero(null);
  setTimeout(() => { setTab(tab); ctx.ready(); }, 0);

  return {
    el,
    hints: [["LB RB", "Switch tab"], ["A", "Open"], ["Y", "Search"], ["B", "Back"]],
    onAction(action) {
      if (action === "tabprev" || action === "tabnext") { setTab(tab === "discover" ? "search" : "discover"); return true; }
      if (action === "search") { setTab("search"); return true; }
      return false;
    },
  };
}
