// Observe the public Game Center in its own anonymous browser. Store network metadata only.
import { randomUUID } from "node:crypto";
import { closeSync, fchmodSync, fstatSync, mkdirSync, openSync, writeSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const [, , gameUrl, logPath, until, kickoff] = process.argv;
const game = URL.canParse(gameUrl) ? new URL(gameUrl) : null;
const endsAt = Date.parse(until);
const kickoffAt = kickoff ? Date.parse(kickoff) : Date.now();
if (game?.origin !== "https://www.nfl.com" || game.href !== game.origin + game.pathname ||
    !/^\/games\/[a-z0-9-]+$/.test(game.pathname) || !logPath ||
    !Number.isFinite(endsAt) || !Number.isFinite(kickoffAt)) {
  console.error("Usage: node scripts/live/capture_nfl_browser.mjs GAME_URL LOG_PATH END_ISO [KICKOFF_ISO]");
  process.exit(2);
}
if (endsAt <= Date.now()) process.exit(0);

const cacheHeaders = new Set([
  "age", "cache-control", "content-encoding", "content-length", "content-type", "date", "etag",
  "expires", "last-modified", "retry-after", "surrogate-control", "via", "x-cache", "x-cache-hits",
  "x-cache-status", "x-served-by", "x-timer", "x-varnish",
]);
const publicQueryKeys = new Set([
  "offset", "season", "seasonType", "type", "week", "includeDriveChart", "includeReplays",
  "includeStandings", "includeTaggedVideos", "operationName", "transport", "EIO",
]);

function route(raw) {
  if (!URL.canParse(raw)) return {};
  const url = new URL(raw);
  if (!["http:", "https:", "ws:", "wss:"].includes(url.protocol)) return { scheme: url.protocol };
  // Short route segments, UUIDs and asset names are useful. Opaque and encoded segments are hidden.
  const path = url.pathname.split("/").map((segment) => {
    const plain = /^[A-Za-z0-9_.-]{0,48}$/.test(segment);
    const opaque = /^[A-Za-z0-9_-]{28,}$/.test(segment) || segment.split(".").length > 3;
    const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(segment);
    const gameSlug = /^[-a-z]+-at-[-a-z]+-20\d\d-(?:reg|post|pre)-\d{1,2}$/.test(segment);
    return plain && (!opaque || uuid || gameSlug) ? segment : "{redacted}";
  }).join("/");
  const params = Object.fromEntries([...url.searchParams].filter(([key, value]) =>
    publicQueryKeys.has(key) && /^[a-z0-9_]{1,36}$/i.test(value)));
  return { scheme: url.protocol, host: url.hostname, path, params };
}

mkdirSync(dirname(logPath), { recursive: true, mode: 0o700 });
const fd = openSync(logPath, "a", 0o600);
fchmodSync(fd, 0o600);
const run = randomUUID();
const stop = new AbortController();
const maxBytes = 128 * 1024 * 1024;
let written = fstatSync(fd).size;
let recording = true;
let disconnected = false;
let fault;
let browser;

function write(event, fields = {}) {
  if (!recording) return;
  const line = JSON.stringify({ at: new Date().toISOString(), run, event, ...fields }) + "\n";
  try {
    if (written >= maxBytes) {
      writeSync(fd, JSON.stringify({ at: new Date().toISOString(), run, event: "capture_full" }) + "\n");
      recording = false;
      stop.abort();
      return;
    }
    written += writeSync(fd, line);
  } catch {
    recording = false;
    fault = "write_failed";
    stop.abort();
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) process.once(signal, () => stop.abort());

try {
  browser = await chromium.launch({
    channel: "chrome",
    args: ["--disable-background-timer-throttling", "--disable-renderer-backgrounding"],
  });
  browser.on("disconnected", () => {
    disconnected = true;
    stop.abort();
  });
  const context = await browser.newContext();
  const page = await context.newPage();
  const requests = new WeakMap();
  let sequence = 0;
  context.on("request", (request) => {
    const id = ++sequence;
    requests.set(request, id);
    write("request", {
      id, ...route(request.url()), method: request.method(), resource: request.resourceType(),
      redirect_from: requests.get(request.redirectedFrom()),
    });
  });
  context.on("response", (response) => {
    const headers = Object.fromEntries(Object.entries(response.headers()).filter(([key]) =>
      cacheHeaders.has(key)));
    write("response", {
      id: requests.get(response.request()), status: response.status(), headers,
      service_worker: response.fromServiceWorker(),
    });
  });
  context.on("requestfinished", async (request) => {
    const id = requests.get(request);
    const timing = request.timing();
    const sizes = await request.sizes().catch(() => null);
    write("finished", { id, elapsed_ms: timing.responseEnd, wire_body_bytes: sizes?.responseBodySize });
  });
  context.on("requestfailed", (request) => {
    const error = request.failure()?.errorText;
    write("failed", {
      id: requests.get(request), error: /^net::ERR_[A-Z_0-9]+$/.test(error) ? error : "REQUEST_FAILED",
    });
  });

  const devtools = await context.newCDPSession(page);
  await devtools.send("Network.enable");
  devtools.on("Network.responseReceived", ({ requestId, response }) => {
    if (response.mimeType === "text/event-stream") {
      write("event_stream", { id: requestId, ...route(response.url), status: response.status });
    }
  });
  devtools.on("Network.eventSourceMessageReceived", ({ requestId, data }) =>
    write("event_stream_message", { id: requestId, bytes: Buffer.byteLength(data) }));
  devtools.on("Network.webSocketCreated", ({ requestId, url }) =>
    write("websocket_open", { id: requestId, ...route(url) }));
  devtools.on("Network.webSocketHandshakeResponseReceived", ({ requestId, response }) =>
    write("websocket_handshake", { id: requestId, status: response.status }));
  for (const [suffix, event] of [["Received", "websocket_received"], ["Sent", "websocket_sent"]]) {
    devtools.on("Network.webSocketFrame" + suffix, ({ requestId, response }) =>
      write(event, { id: requestId, opcode: response.opcode, payload_chars: response.payloadData.length }));
  }
  devtools.on("Network.webSocketClosed", ({ requestId }) => write("websocket_closed", { id: requestId }));
  devtools.on("Network.webTransportCreated", ({ transportId, url }) =>
    write("webtransport_open", { id: transportId, ...route(url) }));
  devtools.on("Network.webTransportConnectionEstablished", ({ transportId }) =>
    write("webtransport_connected", { id: transportId }));
  devtools.on("Network.webTransportClosed", ({ transportId }) =>
    write("webtransport_closed", { id: transportId }));

  async function navigate() {
    try {
      const response = await page.goto(game.href, { waitUntil: "domcontentloaded", timeout: 25000 });
      write("game_page", { ...route(page.url()), status: response?.status() });
    } catch {
      write("game_page_failed");
    }
  }
  write("started", { ...route(game.href), until: new Date(endsAt).toISOString() });
  await navigate();
  let nextRefresh = Math.max(kickoffAt, Date.now() + 120_000);
  let selected = false;
  while (!stop.signal.aborted && Date.now() < endsAt) {
    const reject = page.locator("#onetrust-reject-all-handler").filter({ visible: true }).first();
    if (await reject.isVisible() && await reject.click({ timeout: 3000 }).then(() => true, () => false)) {
      write("optional_cookies_rejected");
    }
    if (!selected) {
      const tab = page.getByRole("tab", { name: /^(play[- ]by[- ]play|all drives)$/i })
        .filter({ visible: true }).first();
      if (await tab.isVisible()) {
        const control = await tab.innerText({ timeout: 3000 }).catch(() => null);
        selected = await tab.click({ timeout: 3000 })
          .then(async () => await tab.getAttribute("aria-selected") === "true", () => false);
        if (selected) write("play_by_play_selected", { ...route(page.url()), control });
      }
      if (!selected && Date.now() >= nextRefresh && Date.now() < kickoffAt + 20 * 60_000) {
        write("refresh_to_find_play_by_play");
        await navigate();
        nextRefresh = Date.now() + 120_000;
      }
    }
    await delay(Math.min(5000, Math.max(0, endsAt - Date.now())), undefined, { signal: stop.signal })
      .catch((error) => { if (error.name !== "AbortError") throw error; });
  }
  if (disconnected) fault = "browser_disconnected";
} catch (error) {
  fault ??= error.name;
} finally {
  write("stopped", { fault });
  await browser?.close();
  recording = false;
  closeSync(fd);
}
if (fault) {
  console.error(`NFL browser capture failed: ${fault}`);
  process.exitCode = 1;
}
