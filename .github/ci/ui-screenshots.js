// Screenshots of the shell in mock mode, with real game art from Steam.
// Usage: node ui-screenshots.js <out dir>   (lumend must be running with LUMEN_MOCK=1)
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

  // First load starts the Steam title lookups for Epic and GOG games.
  await fresh();
  await page.waitForTimeout(15000);

  await fresh();
  await shot("01-home-game");
  await key("ArrowRight");
  await shot("02-home-epic-game");
  await key("ArrowRight", 2);
  await shot("03-home-gog-game");
  await key("ArrowRight");
  await shot("04-home-app");

  await fresh("?view=library");
  await key("ArrowRight", 2);
  await shot("05-library-game");
  await key("ArrowDown", 2);
  await shot("06-library-row-3");
  await key("Enter");
  await shot("07-game-details");
  await browser.close();
})();
