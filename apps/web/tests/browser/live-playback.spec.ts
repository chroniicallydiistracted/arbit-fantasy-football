import { expect, type Locator, type Page, test } from "@playwright/test";
import type { components } from "../../src/generated/api";
import type { Meta } from "../../src/live/scene";

type Animation = components["schemas"]["LiveAnimation"];
type Entry = components["schemas"]["LiveAnimationEntry"];
type GamePlays = components["schemas"]["LivePlays"];

const eventId = "990000001";
const gamePath = `/live/games/${eventId}`;
const home = { team_id: "9901", code: "FIC", score: 7, timeouts: 3 };
const away = { team_id: "9902", code: "TST", score: 3, timeouts: 1 };
const teamArt = (code: string): Meta["teams"]["home"] => ({
  code,
  sprites: { image: `sprites-${code}.png`, rects: {} },
  tag: [
    [238, 238, 228],
    [24, 26, 28],
  ],
  logo: [],
});
const art: Meta = {
  event_id: eventId,
  camera: {
    width: 960,
    height: 540,
    x: 50,
    rise: 36,
    back: 52,
    look: [0, 26],
    focal: 500,
    min_art: 1,
    ball_radius: 5,
    tag_size: 12,
    caption_size: 16,
  },
  band: { top: 0, bottom: 540 },
  board: { top: 6 },
  art_pixel_yards: 0.1,
  cycles: {},
  frames: {},
  ball_offsets: {},
  ball: { image: "ball.png", half: 0.15, width: 0.65 },
  posts: { z: 26, half: 3, crossbar: 3, top: 10, at: [] },
  officials: { image: "officials.png", rects: {} },
  skin_sets: [],
  teams: { home: teamArt(home.code), away: teamArt(away.code) },
  labels: {},
};

function entry(
  playId: string,
  clock: string,
  text: string,
  endX: number,
  part: Entry["part"] = "play",
): Entry {
  const state = { period: 2, clock, home, away, goal_to_go: false };
  return {
    play_id: playId,
    part,
    kind: "pass",
    period: state.period,
    clock,
    text,
    source: "nfl",
    cancelled: false,
    snap_at: null,
    whistle_at: null,
    script: {
      version: 1,
      event_id: eventId,
      provider_id: playId,
      seed: "fictional-browser-playback",
      template: "pass",
      duration: 1.1,
      whistle: 0.4,
      offense: home.team_id,
      defense: away.team_id,
      actors: [],
      ball: [
        { start: 0, end: 0.4, state: "rest", at: [20, 0.2, 26], spin: "flat" },
        { start: 0.4, end: 1.1, state: "rest", at: [endX, 0.2, 26], spin: "flat" },
      ],
      lines: [],
      props: [],
      caption: text,
      label: "Re-creation from play-by-play",
    },
    board: {
      version: 1,
      event_id: eventId,
      provider_id: playId,
      part,
      before: state,
      after: state,
      results: [],
    },
  };
}

async function openPlayback(page: Page, initial: Entry[]) {
  let entries = initial;
  let corrected = new Set<string>();
  let sendEvent: ((event: string) => Promise<void>) | undefined;
  await page.route("**/api/v1/events", (route) => {
    sendEvent = (event) =>
      route.fulfill({
        contentType: "text/event-stream",
        body: `retry: 50\nevent: ${event}\ndata: {}\n\n`,
      });
  });
  await page.route(`**/api/v1${gamePath}/animation`, (route) =>
    route.fulfill({
      json: {
        event_id: eventId,
        home: home.team_id,
        away: away.team_id,
        home_code: home.code,
        away_code: away.code,
        art: { available: true, labels: {} },
        entries,
      } satisfies Animation,
    }),
  );
  await page.route(`**/api/v1${gamePath}/plays?*`, async (route) => {
    const response = await route.fetch();
    const original: GamePlays = await response.json();
    await route.fulfill({
      response,
      json: {
        ...original,
        plays_observed_at: "2026-11-01T17:00:00Z",
        plays: entries
          .filter((play) => play.part === "play")
          .reverse()
          .map((play) => ({
            id: play.play_id,
            period: play.period,
            clock: play.clock,
            text: play.text,
            kind: play.kind,
            own: false,
            scoring: false,
            cancelled: play.cancelled,
            corrected: corrected.has(play.play_id),
            home_score: null,
            away_score: null,
          })),
      } satisfies GamePlays,
    });
  });
  await page.route(`**/api/v1/live/art/${eventId}/meta.json`, (route) =>
    route.fulfill({ json: art }),
  );
  await page.route(`**/api/v1/live/art/${eventId}/*.png`, (route) => {
    const field = route.request().url().endsWith("/field.png");
    const contents = field ? '<rect width="960" height="540" fill="#245b3a"/>' : "";
    return route.fulfill({
      contentType: "image/svg+xml",
      body: `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">${contents}</svg>`,
    });
  });
  await page.goto("/front-office");
  await page.getByRole("button", { name: "Sign in as test member one" }).click();
  await expect(page.getByRole("heading", { name: "Front Office", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Live", exact: true }).first().click();
  await page.getByRole("link", { name: /TST.*FIC/ }).click();
  const field = page.getByRole("region", { name: "Live field" });
  const canvas = field.locator("canvas");
  await expect(canvas).toBeVisible();

  return {
    field,
    canvas,
    async publish(next: Entry[], revisedIds: string[] = []) {
      await expect.poll(() => sendEvent !== undefined).toBe(true);
      const send = sendEvent;
      sendEvent = undefined;
      entries = next;
      corrected = new Set(revisedIds);
      await send?.(revisedIds.length ? "game.corrected" : "game.plays");
    },
  };
}

async function ballX(canvas: Locator) {
  return canvas.evaluate((element: HTMLCanvasElement) => {
    // Below the board, the ball is the only warm-colored part of the synthetic scene.
    const pixels = element.getContext("2d")?.getImageData(0, 200, element.width, 150).data;
    if (!pixels) return -1;
    for (let i = 0; i < pixels.length; i += 4) {
      if (pixels[i] > pixels[i + 1] && pixels[i + 3] === 255) return (i / 4) % element.width;
    }
    return -1;
  });
}

async function boardPixels(canvas: Locator) {
  return canvas.evaluate((element: HTMLCanvasElement) => {
    // The status sits in the top center of the board, apart from the teams and the clock.
    const pixels = element.getContext("2d")?.getImageData(395, 18, 170, 24).data;
    let signature = 0;
    for (const channel of pixels ?? []) signature = (Math.imul(signature, 31) + channel) | 0;
    return signature;
  });
}

test.use({ serviceWorkers: "block" });

test("reduced motion follows successive plays to their ending ball positions", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const first = entry("11", "4:12", "First fictional play.", 50);
  const second = entry("12", "3:50", "Second fictional play.", 60);
  const third = entry("13", "3:23", "Third fictional play.", 70);
  const { field, canvas, publish } = await openPlayback(page, [first]);

  await expect.poll(() => ballX(canvas)).toBeGreaterThan(460);
  await publish([first, second]);
  await expect(field).toContainText("Q2 3:50");
  await expect.poll(() => ballX(canvas)).toBeGreaterThan(520);
  await publish([first, second, third]);
  await expect(field).toContainText("Q2 3:23");
  await expect.poll(() => ballX(canvas)).toBeGreaterThan(580);
  await expect(field.getByRole("button", { name: "Live", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("a play log replay keeps its selection through corrections and cancellation", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const first = entry("21", "4:12", "First fictional play.", 50);
  const selected = entry("22", "3:50", "Fictional touchdown.", 60);
  const attempt = entry("22", "3:49", "Fictional try.", 70, "try");
  const last = entry("23", "3:23", "Latest fictional play.", 80);
  const { field, canvas, publish } = await openPlayback(page, [first, selected, attempt, last]);
  const log = page.getByRole("region", { name: "Plays" });

  await log.getByRole("link", { name: selected.text }).click();
  await expect(log.getByRole("link", { name: selected.text })).toHaveAttribute(
    "aria-current",
    "true",
  );
  await expect(field).toContainText("Q2 3:50");
  await field.getByRole("button", { name: "Next play" }).click();
  await expect(page).toHaveURL(/play=22&part=try/);
  await expect(field).toContainText("Q2 3:49 · Try");

  const inserted = entry("20", "4:30", "Earlier fictional play.", 40);
  const fixed = entry("22", "3:48", "Fictional try with a corrected spot.", 75, "try");
  await publish([inserted, first, selected, fixed, last], ["22"]);
  await expect(page).toHaveURL(/play=22&part=try/);
  await expect(field).toContainText("Q2 3:48 · Try");
  await expect.poll(() => ballX(canvas)).toBeGreaterThan(610);

  await log.getByRole("link", { name: selected.text }).click();
  const cancelled = {
    ...selected,
    cancelled: true,
    script: null,
    text: "Touchdown erased by a hold.",
  };
  await publish([inserted, first, cancelled, last], ["22"]);
  const notice = field.getByRole("status");
  await expect(notice).toContainText("No Play");
  await expect(notice).toContainText(cancelled.text);
  await expect(field.getByRole("button", { name: "Replay" })).toBeDisabled();

  await publish([inserted, first, last], ["22"]);
  await expect(log.getByRole("link", { name: cancelled.text })).toHaveCount(0);
  await expect(notice).toContainText(cancelled.text);
  await expect(page).toHaveURL(/play=22$/);
  await field.getByRole("button", { name: "Live", exact: true }).click();
  await expect(field).toContainText("Q2 3:23");
  await expect(notice).toHaveCount(0);
});

test("a partial replay draws the verified action and explains what is unknown", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const first = entry("31", "4:12", "A catch, followed by a lateral for 9 yards.", 50);
  const partial = {
    ...first,
    script: first.script && {
      ...first.script,
      caption: "First catch.",
      note: "The first catch is shown. See the play text for the lateral and result.",
    },
  };
  const { field, canvas } = await openPlayback(page, [partial]);
  const notice = field.getByRole("status");
  await expect(notice).toContainText("Partial re-creation");
  await expect(notice).toContainText("See the play text for the lateral and result.");
  await expect(notice).toContainText(first.text);
  await expect.poll(() => ballX(canvas)).toBeGreaterThan(460);
});

test("stoppage and final update the existing Jumbotron in place", async ({ page }) => {
  const first = entry("31", "4:12", "Last fictional pass.", 50);
  const { field, canvas, publish } = await openPlayback(page, [first]);
  await expect.poll(() => ballX(canvas)).toBeGreaterThan(460);
  const lastBall = await ballX(canvas);
  const active = await boardPixels(canvas);
  const stoppage = (id: string, status: string): Entry => {
    const play = entry(id, "4:12", status, 50);
    return {
      ...play,
      kind: "administrative",
      script: null,
      board: play.board && { ...play.board, after: { ...play.board.after, status } },
    };
  };
  const timeout = stoppage("32", "TIMEOUT");
  await publish([first, timeout]);
  await expect.poll(() => boardPixels(canvas)).not.toBe(active);
  const timedOut = await boardPixels(canvas);
  await expect.poll(() => ballX(canvas)).toBe(lastBall);

  await publish([first, timeout, stoppage("33", "FINAL")]);
  await expect.poll(() => boardPixels(canvas)).not.toBe(timedOut);
  expect(await boardPixels(canvas)).not.toBe(active);
  await expect.poll(() => ballX(canvas)).toBe(lastBall);
  await expect(field.getByRole("button", { name: "Live", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
