// Shared app state and the polling that keeps it fresh.

import { get } from "./api.js";

export const state = {
  info: { mock: false, live: false, mode: "session" },
  me: null,
  quick: null,
  jobs: [],
  media: null,
  settings: null,
};

const subs = new Set();
export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}
export function changed(key) {
  for (const fn of subs) fn(key);
}

export async function refresh(key, path) {
  try {
    state[key] = await get(path);
    changed(key);
  } catch {
    /* keep the last good value; the daemon may be restarting */
  }
}

let jobTimer = null;
export function pollJobs() {
  clearTimeout(jobTimer);
  refresh("jobs", "jobs").then(() => {
    state.jobs = state.jobs.jobs || state.jobs;
    changed("jobs");
    const running = state.jobs.some((j) => j.state === "running");
    jobTimer = setTimeout(pollJobs, running ? 1000 : 8000);
  });
}

export function applyTheme(settings) {
  if (!settings) return;
  const hex = settings.accent;
  const rgb = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)).join(", ");
  document.documentElement.style.setProperty("--accent", hex);
  document.documentElement.style.setProperty("--accent-rgb", rgb);
  document.getElementById("wall").dataset.wall = settings.wallpaper;
}

let heroTimer = null;
let heroWant = null;

// The wallpaper behind Home and the Library: the focused game's art, or the
// normal aurora for apps and everything else. The image swaps in once it has
// loaded, so moving quickly across tiles never flashes an empty frame.
export function setHero(url) {
  clearTimeout(heroTimer);
  heroWant = url || null;
  const wall = document.getElementById("wall");
  const a = wall.querySelector(".hero.on");
  if (!url) {
    a?.classList.remove("on");
    wall.classList.remove("game");
    return;
  }
  if (a && a.dataset.url === url) return;
  heroTimer = setTimeout(() => {
    const img = new Image();
    img.onload = () => {
      if (heroWant !== url) return;
      const on = wall.querySelector(".hero.on");
      const b = wall.querySelector(".hero:not(.on)");
      b.style.backgroundImage = `url("${url}")`;
      b.dataset.url = url;
      b.classList.remove("on");
      void b.offsetWidth; // restart the slow zoom
      b.classList.add("on");
      on?.classList.remove("on");
      wall.classList.add("game");
    };
    img.src = url;
  }, 120);
}

// Games get their art as the background; apps keep the normal one.
export function setGameHero(item) {
  setHero(item?.kind === "game" ? item.art?.hero || item.art?.cover : null);
}
