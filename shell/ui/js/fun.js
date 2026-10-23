// Right side of the top bar: music, the screenshot album, themes and
// notifications (downloads and installs).

import { get, post } from "./api.js";
import { h, icon } from "./dom.js";
import { openBlade, openSheet } from "./layers.js";
import { applyTheme, changed, refresh, state, subscribe } from "./state.js";

export function openMusic() {
  const blade = openBlade("right", () => {
    const m = state.media;
    if (!m || !m.available) {
      return [h("h2", {}, "Music"), h("div.empty", {}, "Nothing is playing. Start Spotify or any music app and its controls show up here.")];
    }
    const control = (action, ic, auto) => h("button.btn.f.ring", {
      "data-autofocus": auto || null,
      onclick: async () => { state.media = await post("media", { action }); changed("media"); blade.render(); },
    }, icon(ic));
    return [
      h("h2", {}, "Music"),
      h("div.body",
        h(`div.now${m.playing ? "" : ".paused"}`,
          h("div.cover", { style: { backgroundImage: "linear-gradient(135deg, rgba(var(--accent-rgb), .7), #4d63ff)" } },
            h("div.eq", h("i"), h("i"), h("i"), h("i"))),
          h("h3", {}, m.title || "Unknown track"),
          h("p", {}, [m.artist, m.player].filter(Boolean).join(" · ")),
          h("div.media-ctl",
            control("previous", "prev"),
            control("play-pause", m.playing ? "pause" : "play", true),
            control("next", "next")))),
    ];
  });
  refresh("media", "media").then(() => blade.render());
}

export function openAlbum() {
  let shots = null;
  const blade = openBlade("right", () => [
    h("h2", {}, "Album"),
    h("div.body",
      shots === null ? h("div.empty", h("span.spin")) :
      shots.length === 0 ? h("div.empty", {}, "No screenshots yet. Press the Guide and Y buttons together in a game to take one.") :
      h("div.album", { "data-group": true }, shots.map((s) =>
        h("button.shot.f.ring", {
          style: { backgroundImage: `url("${s.path}")` },
          onclick: () => openSheet(({ close }) => [
            h("img", { src: s.path, style: { width: "100%", borderRadius: "1rem" } }),
            h("div.actions", h("button.btn.f.ring", { "data-autofocus": true, onclick: close }, "Close")),
          ], { cls: "detail" }),
        })))),
  ]);
  get("album").then((r) => { shots = r.shots; blade.render(); });
}

export function openThemes() {
  const blade = openBlade("right", () => {
    const s = state.settings;
    const save = async (patch) => {
      state.settings = await post("settings", patch);
      applyTheme(state.settings);
      blade.render();
    };
    return [
      h("h2", {}, "Themes"),
      h("div.body",
        h("div.section-label", {}, "Accent colour"),
        h("div.swatches", { "data-group": true }, Object.entries(s.accents).map(([name, hex]) =>
          h(`button.swatch.f.ring${hex === s.accent ? ".sel" : ""}`, {
            title: name, style: { "--c": hex }, "data-autofocus": hex === s.accent || null,
            onclick: () => save({ accent: hex }),
          }))),
        h("div.section-label", {}, "Background"),
        h("div.walls", { "data-group": true }, s.wallpapers.map((w) =>
          h(`button.wall-opt.f.ring${w === s.wallpaper ? ".sel" : ""}`, {
            style: { background: WALL_PREVIEW[w] }, onclick: () => save({ wallpaper: w }),
          }, w)))),
    ];
  });
}

const WALL_PREVIEW = {
  aurora: "radial-gradient(circle at 20% 20%, rgba(var(--accent-rgb), .7), transparent 60%), radial-gradient(circle at 80% 30%, #4d63ff, transparent 60%), #070a14",
  nebula: "radial-gradient(circle at 20% 20%, #ff5aa0, transparent 60%), radial-gradient(circle at 80% 30%, #4d63ff, transparent 60%), #070a14",
  grid: "linear-gradient(rgba(var(--accent-rgb), .35) 1px, transparent 1px) 0 0 / 1rem 1rem, linear-gradient(90deg, rgba(var(--accent-rgb), .35) 1px, transparent 1px) 0 0 / 1rem 1rem, #070a14",
  dusk: "radial-gradient(circle at 70% 30%, #ff963c, transparent 60%), radial-gradient(circle at 20% 80%, #b43cff, transparent 60%), #070a14",
};

export function openNotifications() {
  let unsub;
  const blade = openBlade("right", () => {
    const jobs = state.jobs || [];
    return [
      h("h2", {}, "Notifications"),
      h("div.body",
        jobs.length === 0 ? h("div.empty", {}, "You're all caught up.") :
        h("div.list", jobs.map((j) => {
          // Automatic updates run in the background with no percentage.
          const auto = j.item_id === "system:auto-update";
          return h("div.job.f.ring",
            h("b", {}, j.title),
            h("small", {}, j.state === "running" ? (auto ? j.message : `${Math.round(j.progress)}% · ${j.message || ""}`)
              : j.state === "done" ? (auto ? j.message : "Finished") : `Failed: ${j.message}`),
            j.state !== "running" ? null
              : auto ? h("div.meter.busy", h("i")) : h("div.meter", h("i", { style: { width: `${j.progress}%` } })));
        }))),
    ];
  }, { onClose: () => unsub?.() });
  unsub = subscribe((k) => k === "jobs" && blade.render());
}
