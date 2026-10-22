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

export function setHero(url) {
  const a = document.querySelector("#wall .hero.on");
  const b = document.querySelector("#wall .hero:not(.on)");
  if (!url) {
    a?.classList.remove("on");
    return;
  }
  if (a && a.dataset.url === url) return;
  b.style.backgroundImage = `url("${url}")`;
  b.dataset.url = url;
  b.classList.add("on");
  a?.classList.remove("on");
}
