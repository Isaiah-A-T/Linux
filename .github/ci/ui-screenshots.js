// Screenshots of the shell in mock mode, with real game art from Steam.
// Usage: node ui-screenshots.js <out dir>   (lumend must be running with LUMEN_MOCK=1)
// The names match docs/screenshots, so a run can be copied straight into the README.
const { chromium } = require("playwright");

const out = process.argv[2];
const base = process.env.LUMEN_URL || "http://127.0.0.1:7777/";

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on("pageerror", (e) => console.log("pageerror:", e.message));
  const key = async (k, n = 1) => {
    for (let i = 0; i < n; i++) { await page.keyboard.press(k); await page.waitForTimeout(200); }
  };
  const shot = async (name) => {
    await page.waitForTimeout(2500); // the background fades in after its image loads
    await page.screenshot({ path: `${out}/${name}.png` });
    console.log(name);
  };
  const fresh = async (q = "") => { await page.goto(base + q); await page.waitForTimeout(2000); };
  const click = async (text) => {
    await page.locator("button:visible", { hasText: text }).first().click();
    await page.mouse.move(0, 0); // so hover doesn't move the focus
    await page.waitForTimeout(400);
  };

  // First load starts the Steam title lookups for Epic and GOG games.
  await fresh();
  await page.waitForTimeout(15000);

  await fresh("?mode=greeter");
  await shot("sign-in");

  // Mock mode starts with the first game (Hades) paused in Quick Resume.
  await fresh();
  await shot("home-game-art");
  await key("ContextMenu");
  await shot("quick-resume");

  await fresh();
  await key("F1");
  await shot("quick-settings");

  await fresh("?view=library");
  await key("ArrowRight", 2);
  await shot("library-game-art");

  // A Steam game's details, then its Proton picker.
  await fresh("?view=library&tab=steam");
  await key("ArrowRight", 2);
  await key("ContextMenu");
  await shot("game-details");
  await click(/Proton/);
  await shot("choose-proton");

  await key("Escape");
  await click("Game settings");
  await shot("game-settings");
  await click("Button layout");
  await shot("game-settings-buttons");

  await fresh("?view=library&tab=accounts");
  await shot("accounts");

  await fresh("?view=settings&page=update");
  await key("ArrowDown");
  await shot("system-update");
  await fresh("?view=settings&page=saves");
  await key("ArrowDown", 2);
  await shot("saves-captures");

  await fresh("?view=store");
  await shot("store");
  await page.locator(".app-card").first().click();
  await page.mouse.move(0, 0);
  await shot("store-app");

  // The on-screen keyboard opens for controllers only, so open it by hand.
  await fresh("?view=store&search=1");
  await page.evaluate(async () => {
    const { openKeyboard } = await import("./js/osk.js");
    openKeyboard(document.querySelector("input.field"));
  });
  await shot("onscreen-keyboard");
  await browser.close();
})();
