// All software (Switch-style grid) with per-source tabs and game accounts.

import { get } from "../api.js";
import { h, icon, SOURCE_LABEL } from "../dom.js";
import { focus, focusFirst } from "../focus.js";
import { install, jobFor, launch, openDetails } from "../details.js";
import { setHero, subscribe } from "../state.js";
import { openAccountSheet } from "./accounts.js";

const TABS = [
  ["all", "All"], ["game", "Games"], ["app", "Apps"],
  ["steam", "Steam"], ["epic", "Epic"], ["gog", "GOG"], ["accounts", "Accounts"],
];

export function render(ctx, params = {}) {
  let tab = params.tab || "all";
  let data = { items: [], counts: {} };
  let accounts = [];
  const tabsEl = h("div.tabs");
  const body = h("div.grid-wrap");
  const el = h("div.view",
    h("div.page-head", h("h1", {}, "Library"), h("div.sub")),
    tabsEl, body);

  function filtered() {
    const items = data.items;
    if (tab === "all") return items;
    if (tab === "game" || tab === "app") return items.filter((i) => i.kind === tab);
    return items.filter((i) => i.source === tab);
  }

  function count(key) {
    if (key === "all") return data.items.length;
    if (key === "game" || key === "app") return data.items.filter((i) => i.kind === key).length;
    if (key === "accounts") return accounts.filter((a) => a.connected).length;
    return data.counts[key] || 0;
  }

  function paintTabs() {
    tabsEl.replaceChildren(
      h("span.glyph.wide.lb", {}, "LB"),
      ...TABS.map(([key, label]) => h(`button.tab.f${key === tab ? ".sel" : ""}`, {
        onclick: () => setTab(key),
      }, label, h("span.n", {}, count(key)))),
      h("span.glyph.wide.rb", {}, "RB"));
  }

  function tile(item) {
    const job = jobFor(item.id);
    const progress = job ? job.progress : item.progress;
    const t = h(`button.tile.f.ring${item.installed ? "" : ".uninstalled"}`, {
      onclick: () => (item.installed && !job ? launch(item) : openDetails(item, { onChange: load })),
    },
      h("div.art", { style: { backgroundImage: `url("${item.art?.cover || item.art?.icon || ""}")` } }),
      h("span.src", {}, item.kind === "app" ? "App" : SOURCE_LABEL[item.source]),
      !item.installed && progress == null ? h("span.dl", icon("download")) : null,
      progress != null ? h("div.bar", h("i", { style: { width: `${progress}%` } })) : null,
      h("span.label", {}, item.title));
    t._item = item;
    return t;
  }

  function paintBody() {
    if (tab === "accounts") {
      body.replaceChildren(
        h("div.accounts", { "data-group": true }, accounts.map((a) =>
          h("button.acct.f.ring", { onclick: () => openAccountSheet(a, (next) => { accounts = next; load(); }) },
            h("div", { class: `logo ${a.id}` }, a.id === "steam" ? "S" : a.id === "epic" ? "E" : "GOG"),
            h("h3", {}, a.name),
            h(`div.state${a.connected ? ".ok" : ""}`, {}, a.connected ? `Signed in as ${a.user || "you"}` : a.available ? "Not connected" : "Not installed"),
            h("div.cta", {}, a.connected ? "Manage" : "Connect", icon("chevron"))))),
        h("div.note", {},
          "Connected stores add their games to your library. Steam games run through Steam and its own Proton. " +
          "Epic and GOG games download to ~/Games and run with GE-Proton, each in its own Wine prefix, so there's nothing else to set up."));
      return;
    }
    const items = filtered();
    if (!items.length) {
      const src = SOURCE_LABEL[tab];
      body.replaceChildren(h("div.empty", {},
        src && tab !== "app" ? `No ${src} games yet. Connect your ${src} account in Accounts.` : "Nothing here yet."));
      return;
    }
    body.replaceChildren(h("div.grid", { "data-group": true }, items.map(tile)));
  }

  function setTab(key) {
    tab = key;
    paintTabs();
    paintBody();
    body.scrollTop = 0;
    focusFirstIn(body);
  }

  function focusFirstIn(root) {
    const first = root.querySelector(".f");
    if (first) focus(first);
    else focusFirst();
  }

  function cycle(step) {
    const i = TABS.findIndex(([k]) => k === tab);
    setTab(TABS[(i + step + TABS.length) % TABS.length][0]);
  }

  async function load() {
    [data, { accounts }] = await Promise.all([get("library"), get("accounts")]);
    el.querySelector(".sub").textContent = `${data.items.filter((i) => i.installed).length} installed · ${data.items.length} total`;
    const keep = document.querySelector(".focused")?._item?.id;
    paintTabs();
    paintBody();
    const again = keep && [...body.querySelectorAll(".tile")].find((t) => t._item?.id === keep);
    if (again) focus(again, { scroll: false });
  }

  const unsub = subscribe((key) => {
    if (key === "jobs" && tab !== "accounts") {
      const keep = document.querySelector(".focused")?._item?.id;
      paintBody();
      const again = keep && [...body.querySelectorAll(".tile")].find((t) => t._item?.id === keep);
      if (again) focus(again, { scroll: false });
    }
  });

  paintTabs();
  load().then(() => { focusFirstIn(body); ctx.ready(); });
  setHero(null);

  return {
    el,
    hints: [["LB RB", "Switch tab"], ["A", "Play"], ["X", "Details"], ["B", "Back"]],
    onAction(action, f) {
      if (action === "tabprev") { cycle(-1); return true; }
      if (action === "tabnext") { cycle(1); return true; }
      if (action === "options" && f?._item) { openDetails(f._item, { onChange: load }); return true; }
      return false;
    },
    destroy: unsub,
  };
}

export { install };
