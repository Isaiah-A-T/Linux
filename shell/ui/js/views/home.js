// Home: the 15 most recent games and apps, then the dock.

import { get, post } from "../api.js";
import { h, icon, SOURCE_LABEL, timeAgo } from "../dom.js";
import { focus, onFocus } from "../focus.js";
import { openDetails, launch } from "../details.js";
import { confirmSheet, toast } from "../layers.js";
import { openPower } from "../quick.js";
import { setHero, state } from "../state.js";

export function render(ctx) {
  const kicker = h("div.kicker");
  const title = h("h1");
  const meta = h("div.meta");
  const hero = h("div.home-hero", h("div.fade", kicker, title, meta));
  const row = h("div.row", { "data-group": true });
  const dock = h("div.dock", { "data-group": true });
  const el = h("div.view.home", hero, row, dock);

  function showHero(item) {
    const fade = h("div.fade");
    if (item) {
      fade.append(
        h("div.kicker", {}, item.kind === "app" ? "App" : SOURCE_LABEL[item.source] || ""),
        h("h1", {}, item.title),
        h("div.meta", {}, timeAgo(item.last_played)));
      setHero(item.art?.hero || item.art?.cover);
    } else {
      fade.append(h("div.kicker", {}, "Lumen"), h("h1", {}, greeting()), h("div.meta", {}, "Your library, apps and store, all in one place."));
      setHero(null);
    }
    hero.replaceChildren(fade);
  }

  const off = onFocus((f) => {
    if (!el.contains(f)) return;
    showHero(f._item || null);
  });

  get("home").then(({ items }) => {
    const tiles = items.map((item, i) => {
      const t = h(`button.tile.f.ring${i === 0 ? ".big" : ""}`, {
        "data-autofocus": i === 0 || null,
        onclick: () => launch(item),
      },
        h("div.art", { style: { backgroundImage: `url("${item.art?.cover || item.art?.icon || ""}")` } }),
        h("span.src", {}, item.kind === "app" ? "App" : SOURCE_LABEL[item.source]),
        h("span.label", {}, item.title));
      t._item = item;
      t.style.animation = `heroText .5s var(--ease) ${0.03 * i}s both`;
      return t;
    });
    const all = h("button.tile.all.f.ring", { onclick: () => ctx.go("library") },
      h("div", icon("grid"), h("span", {}, "All software")));
    row.replaceChildren(...tiles, all);
    if (!document.querySelector(".blade, .sheet")) focus(tiles[0] || all);
    if (!items.length) showHero(null);
    ctx.ready();
  });

  const dockBtn = (label, ic, onclick, cls = "") =>
    h(`button.dock-btn.f${cls}`, { onclick }, h("span.circle", icon(ic)), h("span", {}, label));
  dock.append(...[
    dockBtn("Library", "grid", () => ctx.go("library")),
    dockBtn("Store", "bag", () => ctx.go("store")),
    state.info.live ? dockBtn("Install Lumen OS", "install", async () => {
      if (await confirmSheet({ title: "Install Lumen OS?", text: "The installer walks you through it. Nothing changes until you confirm the disk.", ok: "Start installer" })) {
        post("install-os").catch((e) => toast(e.message));
      }
    }, ".install") : null,
    dockBtn("Power", "power", openPower)].filter(Boolean));

  showHero(null);

  return {
    el,
    hints: [["A", "Play"], ["X", "Options"], ["Y", "Search store"]],
    onAction(action, focusedEl) {
      if (action === "options" && focusedEl?._item) {
        openDetails(focusedEl._item);
        return true;
      }
      if (action === "search") {
        ctx.go("store", { search: true });
        return true;
      }
      return false;
    },
    destroy: off,
  };
}

function greeting() {
  const hr = new Date().getHours();
  const name = state.me?.name || "";
  return `${hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening"}, ${name}`;
}
