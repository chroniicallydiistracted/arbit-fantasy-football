// Times the browser leg of live plays (R-042): server event received, plays re-fetched with the new
// play, and the play's text on screen. Uses the read-only dev account on the local port, one browser
// profile per tab. Wall times are epoch ms from this machine's clock, the clock the worker stamps its
// publications with. Cloudflare Access blocks automation on the public address.
//
//   STATE=<copy of data/observer/storage-state.json with the cookie's domain 127.0.0.1, secure false, mode 600>
//   ARBIT_BROWSER_PATH=<headless shell> node scripts/live/time_browser_leg.cjs "$STATE" out.jsonl 720 <event ids...>
//   uv run python scripts/live/browser_leg_report.py out.jsonl data/nfl-api/live-log/<UTC day>.jsonl
const fs = require("node:fs");
const { createRequire } = require("node:module");
const req = createRequire(require("node:path").resolve(__dirname, "../../apps/web/package.json"));
const { chromium } = req("@playwright/test");

const [, , stateFile, outFile, seconds, ...events] = process.argv;
const out = fs.openSync(outFile, "w", 0o600);
const log = (row) => fs.writeSync(out, `${JSON.stringify(row)}\n`);

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.ARBIT_BROWSER_PATH });
  // One profile per tab: each tab's open event stream counts against its profile's six HTTP/1.1
  // connections to the local port, so shared tabs would starve each other's requests.
  for (const event of events) {
    const context = await browser.newContext({ storageState: stateFile, viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    let offset = null; // wall seconds minus monotonic seconds
    const requests = new Map();
    const known = new Set();
    let first = true;
    const wall = (mono) => (offset === null ? null : Math.round((mono + offset) * 1000));
    cdp.on("Network.requestWillBeSent", (e) => {
      if (offset === null && e.wallTime) offset = e.wallTime - e.timestamp;
      requests.set(e.requestId, { url: e.request.url, sent: e.timestamp });
    });
    cdp.on("Network.eventSourceMessageReceived", (e) => {
      log({ tab: event, kind: "sse", name: e.eventName, data: e.data, at: wall(e.timestamp) });
    });
    cdp.on("Network.loadingFinished", async (e) => {
      const r = requests.get(e.requestId);
      if (!r) return;
      const path = new URL(r.url).pathname;
      if (!/^\/api\/v1\/live\/games\/[^/]+\/(plays|animation)$/.test(path)) return;
      const row = { tab: event, kind: "fetch", path, sent: wall(r.sent), done: wall(e.timestamp) };
      if (path.endsWith("/plays")) {
        try {
          const { body } = await cdp.send("Network.getResponseBody", { requestId: e.requestId });
          const plays = JSON.parse(body).plays || [];
          const fresh = plays.filter((p) => !known.has(p.id) && !p.cancelled);
          for (const p of plays) known.add(p.id);
          row.new = first ? [] : fresh.map((p) => p.id);
          if (!first) {
            for (const p of fresh) {
              const snippet = (p.text || "").slice(0, 40);
              if (snippet.length < 12) continue;
              page
                .waitForFunction((s) => document.body.innerText.includes(s), snippet, { polling: 50, timeout: 90_000 })
                .then(() => log({ tab: event, kind: "screen", id: p.id, at: Date.now() }))
                .catch(() => log({ tab: event, kind: "screen-timeout", id: p.id }));
            }
          }
          first = false;
        } catch (error) {
          row.error = String(error).slice(0, 120);
        }
      }
      log(row);
    });
    await page.goto(`http://127.0.0.1:8000/live/games/${event}`, { waitUntil: "domcontentloaded" });
  }
  log({ kind: "started", at: Date.now() });
  await new Promise((resolve) => setTimeout(resolve, Number(seconds) * 1000));
  log({ kind: "stopped", at: Date.now() });
  await browser.close();
  fs.closeSync(out);
})();
