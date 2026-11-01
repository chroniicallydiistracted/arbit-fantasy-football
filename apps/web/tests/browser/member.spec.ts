import { readFile, writeFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function login(page: Page, member: "one" | "two" = "one") {
  await page.goto("/front-office");
  await page.getByRole("button", { name: `Open preview · Member ${member}` }).click();
  await expect(page.getByRole("heading", { name: "Front Office.", exact: true })).toBeVisible();
  const status = await page.request.get("/auth/status").then((response) => response.json());
  const me = await page.request.get("/api/v1/me").then((response) => response.json());
  await page.request.put("/api/v1/me/preferences", {
    headers: { Origin: "http://127.0.0.1:8000", "X-CSRF-Token": status.csrf_token },
    data: { version: me.preferences.version, theme: "system", watchlist: [] },
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Front Office.", exact: true })).toBeVisible();
}
async function openMenu(page: Page) {
  const menu = page.getByRole("button", { name: "Toggle navigation" });
  if (await menu.isVisible()) await menu.click();
}

test("two members, official nulls, historical context, player focus, private watchlist and sign-out", async ({
  page,
  browser,
}) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Fictional Juniper Club" })).toBeVisible();
  await expect(page.locator(".matchup-score").first()).toContainText("—");
  await page.getByLabel("Fantasy matchup").selectOption("7");
  await expect(
    page.getByRole("heading", { name: "That roster hasn’t been captured." }),
  ).toBeVisible();
  await expect(page.locator(".matchup-score").first()).toContainText("128.25");
  await page.getByLabel("Fantasy matchup").selectOption("8");
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
  await page.getByRole("button", { name: "Evening green" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await openMenu(page);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
  expect(
    await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })),
  ).toEqual({ local: 0, session: 0 });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Welcome back." })).toBeVisible();
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
      await expect(page.getByRole("button", { name: "Toggle navigation" })).toHaveAttribute(
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
  await expect(page.getByRole("heading", { name: "Front Office.", exact: true })).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "Reconnect to open your front office." }),
  ).toBeVisible();
  await expect(page.getByText("Fictional Juniper Club", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your front office will be here when you reconnect." }),
  ).toBeVisible();
  await context.setOffline(false);
  await page.goto("/front-office");
  await expect(page.getByRole("heading", { name: "Front Office.", exact: true })).toBeVisible();
  const path = new URL("../../dist/sw.js", import.meta.url);
  const original = await readFile(path, "utf8");
  try {
    await writeFile(path, original.replace(/arbit-static-[a-f0-9]+/, "arbit-static-browser-test"));
    await page.evaluate(async () => {
      await (await navigator.serviceWorker.getRegistration())?.update();
    });
    await expect(page.getByRole("button", { name: "Update & reload" })).toBeVisible();
    await page.getByRole("button", { name: "Update & reload" }).click();
    await expect(page.getByRole("heading", { name: "Front Office.", exact: true })).toBeVisible();
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
    page.getByRole("heading", { name: "The league view is unavailable.", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".own-team h3")).toHaveCount(0);
  await page.getByRole("link", { name: "Return to your team" }).click();
  await expect(page.locator(".own-team h3")).toHaveText("Fictional Copper Owls");
  await page.getByLabel("Find a player").fill("Ja'Marr");
  await expect(
    page.getByText("No players match that name. Try a different spelling."),
  ).toBeVisible();
  await expect(page.getByText("Search unavailable", { exact: true })).toHaveCount(0);
});
