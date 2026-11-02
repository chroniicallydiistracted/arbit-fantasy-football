import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function login(page: Page, member: "one" | "two" = "one") {
  await page.goto("/front-office");
  await page.getByRole("button", { name: `Sign in as test member ${member}` }).click();
  await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
  const status = await page.request.get("/auth/status").then((response) => response.json());
  const me = await page.request.get("/api/v1/me").then((response) => response.json());
  await page.request.put("/api/v1/me/preferences", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": status.csrf_token },
    data: { version: me.preferences.version, theme: "system", watchlist: [] },
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
}
async function openMenu(page: Page) {
  const menu = page.getByRole("button", { name: "More", exact: true });
  if (await menu.isVisible()) await menu.click();
}

test("two members, official nulls, historical context, player focus, private watchlist and sign-out", async ({
  page,
  browser,
}) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Fictional Juniper Club" })).toBeVisible();
  await expect(page.locator(".matchup-score").first()).toContainText("—");
  await page.getByRole("link", { name: /^Matchup 7/ }).click();
  await expect(
    page.getByRole("heading", { name: "No roster saved for this matchup" }),
  ).toBeVisible();
  await expect(page.locator(".matchup-score").first()).toContainText("128.25");
  await page.getByRole("link", { name: /^Matchup 8/ }).click();
  await page.getByLabel("Position", { exact: true }).selectOption("QB");
  const player = page.getByRole("button", { name: /^Avery Juniper/ });
  await player.click();
  const panel = page.getByRole("dialog", { name: "Avery Juniper" });
  await expect(panel).toBeVisible();
  await panel.getByRole("button", { name: /watchlist/ }).click();
  await expect(panel.getByRole("button", { name: /watchlist/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.keyboard.press("Escape");
  await expect(panel).not.toBeVisible();
  await expect(player).toBeFocused();
  await expect(page.getByLabel("Position", { exact: true })).toHaveValue("QB");
  const other = await browser.newContext();
  const second = await other.newPage();
  await login(second, "two");
  await expect(second.locator(".own-team h3")).toHaveText("Fictional Copper Owls");
  const firstMe = await page.request.get("/api/v1/me").then((response) => response.json());
  const denied = await second.request.get(`/api/v1/front-office?team_id=${firstMe.team_id}`);
  expect(denied.status()).toBe(403);
  expect(
    (await second.request.get("/api/v1/me").then((response) => response.json())).preferences
      .watchlist,
  ).toEqual([]);
  await other.close();
  await openMenu(page);
  await page.getByRole("link", { name: "Preferences", exact: true }).click();
  await page.getByRole("button", { name: "Dark", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await openMenu(page);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign in as test member one" })).toBeVisible();
  expect(
    await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })),
  ).toEqual({ local: 0, session: 0 });
  await page.reload();
  await expect(page.getByRole("button", { name: "Sign in as test member one" })).toBeVisible();
});

for (const width of [320, 768, 1280, 1600]) {
  test(`accessible facts and no horizontal page overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await login(page);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(result.violations).toEqual([]);
    await page.screenshot({
      path: `../../.superpowers/sdd/2026-10-31-member-application/front-office-${width}.png`,
      fullPage: true,
    });
    await page.getByRole("button", { name: "Avery Juniper", exact: true }).click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.keyboard.press("Escape");
    if (width === 320) {
      await openMenu(page);
      await page.keyboard.press("Escape");
      await expect(page.getByRole("button", { name: "More", exact: true })).toHaveAttribute(
        "aria-expanded",
        "false",
      );
    }
    if (width === 1280) {
      await page.evaluate(() => {
        document.documentElement.style.fontSize = "200%";
      });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
    }
  });
}

test("static-only install cache, offline private clearing and explicit update", async ({
  page,
  context,
}) => {
  await login(page);
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
  await page.evaluate(async () => {
    await fetch("/api/v1/me", { cache: "no-store" });
  });
  const urls = await page.evaluate(async () =>
    (
      await Promise.all(
        (
          await caches.keys()
        ).map(async (name) =>
          (await (await caches.open(name)).keys()).map((request) => new URL(request.url).pathname),
        ),
      )
    ).flat(),
  );
  expect(urls.length).toBeGreaterThan(3);
  expect(
    urls.every((url) =>
      /^(\/assets\/|\/offline\.(html|css)$|\/icon-\d+\.png$|\/mark.svg$|\/manifest.webmanifest$)/.test(
        url,
      ),
    ),
  ).toBe(true);
  await context.setOffline(true);
  await expect(page.getByRole("heading", { name: "Offline", exact: true })).toBeVisible();
  await expect(page.getByText("Fictional Juniper Club", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Offline", exact: true })).toBeVisible();
  await context.setOffline(false);
  await page.goto("/front-office");
  await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
  const path = process.env.ARBIT_WEB_DIST_PATH
    ? `${process.env.ARBIT_WEB_DIST_PATH}/sw.js`
    : new URL("../../dist/sw.js", import.meta.url);
  const original = await readFile(path, "utf8");
  try {
    await writeFile(path, original.replace(/arbit-static-[a-f0-9]+/, "arbit-static-browser-test"));
    await page.evaluate(async () => {
      await (await navigator.serviceWorker.getRegistration())?.update();
    });
    await expect(page.getByRole("button", { name: "Update & reload" })).toBeVisible();
    await page.getByRole("button", { name: "Update & reload" }).click();
    await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
  } finally {
    await writeFile(path, original);
  }
});

test("a shared-cookie account switch clears a fresh private deep link before showing the new member", async ({
  page,
}) => {
  await login(page);
  const original = await page.request.get("/api/v1/me").then((response) => response.json());
  await page.goto(`/front-office?team=${original.team_id}`);
  await expect(page.locator(".own-team h3")).toHaveText("Fictional Juniper Club");
  await page.evaluate(async () => {
    // Dedicated fixture endpoint only: equivalent shared-cookie replacement to a
    // different member completing the provider flow in a second tab.
    const response = await fetch("/auth/fixture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ member: "two" }),
    });
    if (!response.ok) throw new Error("Fictional account replacement failed");
    window.dispatchEvent(new Event("focus"));
  });
  await expect(page.locator(".member-label strong")).toHaveText("Fictional member two");
  await expect(
    page.getByRole("heading", { name: "League data unavailable", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".own-team h3")).toHaveCount(0);
  await page.getByRole("link", { name: "Your team" }).click();
  await expect(page.locator(".own-team h3")).toHaveText("Fictional Copper Owls");
  await page.getByLabel("Search players").fill("Ja'Marr");
  await expect(page.getByText("No players match that name.")).toBeVisible();
  await expect(page.getByText("Search unavailable", { exact: true })).toHaveCount(0);
});

test("an open client updates without a reload when the server publishes a change", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "Live", exact: true }).first().click();
  const tile = page.locator(".game-tile").first();
  await expect(tile).toContainText("FIC");
  await expect(tile).toContainText("7");
  let navigations = 0;
  page.on("framenavigated", () => {
    navigations += 1;
  });
  const score = String(10 + Math.floor(Math.random() * 80));
  // Same publication path as the worker, in the dedicated fixture database.
  execFileSync("uv", ["run", "python", "-m", "arbit_api.fixture", "live-score", score], {
    cwd: new URL("../../../../", import.meta.url).pathname,
    stdio: "ignore",
  });
  await expect(tile.locator(".game-line").last()).toContainText(score, { timeout: 8000 });
  expect(navigations).toBe(0);
  await expect(page.getByText("Reconnecting")).toHaveCount(0);
});

test("the Live workspace deep-links to a game and survives a hard reload", async ({ page }) => {
  await login(page);
  await page.goto("/live/games/990000001");
  await expect(page.getByRole("heading", { name: "TST at FIC" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "TST at FIC" })).toBeVisible();
  // The scoreboard states the live situation in words, on the field and by quarter.
  const board = page.locator(".game-board");
  await expect(board.locator(".gb-down")).toContainText("3rd & 7");
  await expect(board.locator(".gb-down")).toContainText("FIC 38");
  await expect(board.getByRole("img", { name: /Ball at FIC 38/ })).toBeVisible();
  await expect(board.getByRole("table", { name: "Score by quarter" })).toContainText("Q2");
  await expect(page.getByRole("img", { name: /win probability/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Drives" })).toBeVisible();
  for (const width of [320, 768, 1280]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/live/games/990000001");
    await expect(board).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `game page overflows at ${width}px`).toBeLessThanOrEqual(0);
  }
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(result.violations).toEqual([]);
});

test("another name for this machine opens the app where sign-in works", async ({
  page,
  baseURL,
}) => {
  const own = new URL(baseURL ?? "");
  test.skip(own.hostname !== "127.0.0.1", "needs the app's own address to be 127.0.0.1");
  await page.goto(`http://localhost:${own.port}/live?from=bookmark`);
  await expect(page).toHaveURL(`${own.origin}/live?from=bookmark`);
  await page.getByRole("button", { name: "Sign in as test member one" }).click();
  await expect(page.getByRole("heading", { name: "Live", exact: true })).toBeVisible();
  const cookies = await page.context().cookies(own.origin);
  expect(cookies.map((cookie) => cookie.name)).toContain("arbit_session");
});

test("a member can see and end their own signed-in devices", async ({ page }) => {
  await login(page);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Signed-in devices" })).toBeVisible();
  await expect(page.locator(".device-list li").first()).toContainText("This device");
});
