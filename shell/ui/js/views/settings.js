// Settings: the things you don't need every day. Wi-Fi and Bluetooth live in
// Quick Settings and game accounts in the Library; Settings links to them.

import { get } from "../api.js";
import { fmtBytes, h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { openQuickSettings } from "../quick.js";
import { setHero, state } from "../state.js";

export function render(ctx) {
  let page = "storage";
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
  return { el, hints: [["A", "Select"], ["B", "Back"]] };
}
