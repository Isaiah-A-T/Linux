// Per-game settings, opened from a game's details: frame rate cap, power mode
// and button layout. lumend applies them when the game starts and puts the
// system back when you return to the shell.

import { get, post } from "./api.js";
import { h, icon } from "./dom.js";
import { openBlade, toast } from "./layers.js";

const NEEDS = {
  fps: "Needs gamescope and xprop",
  power: "Needs power-profiles-daemon",
  remap: "Needs InputPlumber",
};

// onBack runs when B is pressed on the first page (e.g. reopen the game's details).
export function openGameSettings(item, { onBack } = {}) {
  let data = null;
  let page = "main";
  let error = "";
  // The row a sub-page was opened from, so coming back lands on it again.
  let opener = null;

  const s = () => data.settings;
  const buttonLabel = (id) => data.options.buttons.find((b) => b.id === id)?.label || id;
  const fpsLabel = (fps) => (fps ? `${fps} FPS` : "Off");
  const powerLabel = (id) => data.options.power.find((p) => p.id === id)?.label || id;

  async function save(change, next) {
    error = "";
    try {
      data = await post("game-settings", { id: item.id, ...change });
    } catch (e) {
      error = e.message;
    }
    if (next) back(next);
    else blade.render();
  }

  function go(p) {
    opener = page;
    page = p;
    error = "";
    blade.render();
  }

  // Up a level, focusing the row that opened the page we leave.
  function back(to) {
    opener = page;
    page = to;
    error = "";
    blade.render();
  }
  const from = (p) => opener === p || null;

  function header(title, parent = "main") {
    return h("h2", {}, h("button.back.f.ring", { onclick: () => back(parent) }, icon("back")), title);
  }

  // A row in a pick list: the current choice gets the check mark and focus.
  function choice(label, detail, selected, onclick) {
    return h("button.item.f.ring", { "data-autofocus": selected || null, onclick },
      h("div.grow", h("b", {}, label), detail ? h("small", {}, detail) : null),
      selected ? h("span.tag", {}, "✓") : null);
  }

  function row(ic, label, value, onclick, need, autofocus) {
    return h("button.item.f.ring", { disabled: !!need, onclick, "data-autofocus": autofocus },
      icon(ic), h("div.grow", h("b", {}, label), h("small", {}, need || value)), icon("chevron"));
  }

  function changedCount() {
    return Object.keys(s().remap).length;
  }

  const pages = {
    main() {
      const sup = data.support;
      const n = changedCount();
      const custom = s().fps || s().power !== "default" || n;
      return [
        h("h2", {}, "Game settings"),
        h("p.gs-title", {}, item.title),
        h("div.body.page-in",
          h("div.section-label", { style: { marginTop: 0 } }, "Performance"),
          h("div.list",
            row("gauge", "Frame rate cap", fpsLabel(s().fps), () => go("fps"), !sup.fps && NEEDS.fps, from("fps")),
            row("leaf", "Power mode", powerLabel(s().power), () => go("power"), !sup.power && NEEDS.power, from("power"))),
          h("div.section-label", {}, "Controls"),
          h("div.list",
            row("pad", "Button layout", n ? `${n} button${n === 1 ? "" : "s"} changed` : "Default",
              () => go("controls"), !sup.remap && NEEDS.remap, from("controls"))),
          item.source === "steam" ? h("p.gs-note", {},
            "If Steam Input is turned on for this game, Steam's own layout is used on top of this one.") : null,
          custom ? h("button.item.f.ring", { onclick: () => save({ fps: null, power: "default", remap: {} }) },
            icon("restart"), h("div.grow", h("b", {}, "Reset to default"))) : null,
          h("p.gs-note", {}, "These apply when the game starts and switch back when you return to Lumen."),
          h("div.err", {}, error)),
      ];
    },

    fps() {
      return [
        header("Frame rate cap"),
        h("div.body.page-in",
          h("p.gs-note", {}, "A lower cap keeps the fans quieter and the battery going longer."),
          h("div.list",
            choice("Off", "As fast as the game can go", !s().fps, () => save({ fps: null }, "main")),
            data.options.fps.map((fps) => choice(`${fps} FPS`, null, s().fps === fps, () => save({ fps }, "main")))),
          h("div.err", {}, error)),
      ];
    },

    power() {
      return [
        header("Power mode"),
        h("div.body.page-in",
          h("div.list", data.options.power.map((p) =>
            choice(p.label, p.detail, s().power === p.id, () => save({ power: p.id }, "main")))),
          h("div.err", {}, error)),
      ];
    },

    controls() {
      const remap = s().remap;
      const same = (m) => Object.keys(m).length === Object.keys(remap).length &&
        Object.entries(m).every(([k, v]) => remap[k] === v);
      return [
        header("Button layout"),
        h("div.body.page-in",
          h("div.section-label", {}, "Quick layouts"),
          h("div.list",
            choice("Default", "Every button does what it says", !Object.keys(remap).length, () => save({ remap: {} })),
            data.options.presets.map((p) => choice(p.label, p.detail, same(p.remap), () => save({ remap: p.remap })))),
          h("div.section-label", {}, "Buttons"),
          h("div.list", data.options.buttons.map((b) =>
            h("button.item.f.ring", { onclick: () => go(`pick:${b.id}`), "data-autofocus": from(`pick:${b.id}`) },
              h("span.glyph.wide.gs-glyph", {}, b.label),
              h("div.grow",
                h("b", {}, remap[b.id] ? (remap[b.id] === "off" ? "Turned off" : `Acts as ${buttonLabel(remap[b.id])}`) : b.label),
                remap[b.id] ? h("small", {}, "Changed") : null),
              icon("chevron")))),
          h("div.err", {}, error)),
      ];
    },

    pick(id) {
      const current = s().remap[id];
      const set = (to) => {
        const remap = { ...s().remap };
        if (to === id) delete remap[id];
        else remap[id] = to;
        save({ remap }, "controls");
      };
      return [
        header(`${buttonLabel(id)} acts as`, "controls"),
        h("div.body.page-in",
          h("div.list",
            choice(buttonLabel(id), "Default", !current, () => set(id)),
            data.options.buttons.filter((b) => b.id !== id).map((b) =>
              choice(b.label, null, current === b.id, () => set(b.id))),
            choice("Nothing", "The button does nothing in this game", current === "off", () => set("off"))),
          h("div.err", {}, error)),
      ];
    },
  };

  const blade = openBlade("right", () => {
    if (!data) return [h("h2", {}, "Game settings"), h("div.empty", h("span.spin"))];
    const [name, arg] = page.split(":");
    return pages[name](arg);
  }, {
    onAction(action) {
      if (action !== "back") return false;
      if (page !== "main") back(page.startsWith("pick:") ? "controls" : "main");
      else {
        blade.close();
        onBack?.();
      }
      return true;
    },
    hints: [["A", "Select"], ["B", "Back"]],
  });

  get(`game-settings?id=${encodeURIComponent(item.id)}`)
    .then((d) => { data = d; blade.render(); })
    .catch((e) => { toast(e.message, icon("info")); blade.close(); });
  return blade;
}
