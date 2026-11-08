import { expect, it } from "vitest";
import { MotionScene, type MotionScript } from "./motion_scene";
import type { Art } from "./scene";

const art = {
  meta: {
    camera: {
      width: 960,
      height: 540,
      x: 50,
      rise: 35,
      back: 50,
      look: [0, 26],
      focal: 500,
      min_art: 1,
    },
    band: { top: 100, bottom: 540 },
    art_pixel_yards: 0.09,
    frames: { ready: { w: 18, h: 28, torso: 8, near_hand: [13, 8], chest: [9, 10] } },
    cycles: {},
    posts: { at: [] },
  },
} as unknown as Art;

const script: MotionScript = {
  version: 2,
  event_id: "1",
  provider_id: "2",
  template: "run",
  duration: 4,
  whistle: 3,
  motion_end: 2.6,
  offense: "1",
  defense: "2",
  actors: [
    {
      key: "qb",
      side: "offense",
      role: "quarterback",
      track: [{ t: 0, x: 28, z: 27, vx: 0, vz: 0, heading: 0 }],
      poses: [{ start: 0, pose: "ready" }],
    },
    {
      key: "back",
      side: "offense",
      role: "rusher",
      track: [
        { t: 0, x: 27, z: 28, vx: 0, vz: 0, heading: 1.5 },
        { t: 2, x: 29, z: 28, vx: 4, vz: 0, heading: 1.5 },
      ],
      poses: [{ start: 0, pose: "ready" }],
    },
  ],
  ball: [
    { start: 0, end: 1.6, style: "held", origin: { actor: "qb", hold: "hand" } },
    {
      start: 1.6,
      end: 1.8,
      style: "exchange",
      origin: { actor: "qb", hold: "hand" },
      target: { actor: "back", hold: "chest" },
    },
    { start: 1.8, end: 4, style: "held", origin: { actor: "back", hold: "chest" } },
  ],
  milestones: [],
  timing: { overrun: 0, unfilled: 0 },
  lines: [],
  caption: "Fictional handoff",
  label: "Re-creation from play-by-play",
};

it("keeps the visible ball continuous when held, exchanged and caught", () => {
  const scene = new MotionScene(script, art, "1");
  for (const time of [1.6, 1.8]) {
    const before = scene.ball(time - 0.000001);
    const after = scene.ball(time);
    if (!before || !after) throw new Error("Ball missing at the handoff boundary");
    expect(Math.hypot(...before.at.map((value, i) => value - after.at[i]))).toBeLessThan(0.001);
  }
  const held = scene.ball(1.9);
  expect(held?.depth).toBe(28);
  expect(scene.ball(5)?.at).toEqual(scene.ball(4)?.at);
});

it("keeps an estimated high kickoff arc inside the field canvas", () => {
  const shot = { ...art, meta: { ...art.meta, band: { top: 160, bottom: 540 } } };
  const scene = new MotionScene(
    {
      ...script,
      ball: [
        {
          start: 0,
          end: 4,
          style: "kick",
          origin: { point: [35, 0.25, 26] },
          target: { point: [95, 1.5, 26] },
        },
      ],
    },
    shot,
    "1",
  );
  for (let i = 0; i < 80; i += 1) {
    const ball = scene.ball(i / 20);
    if (!ball) throw new Error("Kickoff ball is missing");
    expect(scene.camera.project(...ball.at)[1]).toBeGreaterThanOrEqual(shot.meta.band.top + 4);
  }
});

it("slows a rolling ball continuously into its resting spot", () => {
  const scene = new MotionScene(
    {
      ...script,
      ball: [
        {
          start: 0,
          end: 1,
          style: "roll",
          origin: { point: [100, 0.15, 26] },
          target: { point: [104, 0.15, 26] },
        },
        { start: 1, end: 4, style: "rest", origin: { point: [104, 0.15, 26] } },
      ],
    },
    art,
    "1",
  );
  expect(scene.ball(0.5)?.at[0]).toBe(103);
  expect(scene.ball(1)?.at).toEqual([104, 0.15, 26]);
});

it("projects the same ten-yard displacement consistently at each depth", () => {
  const { camera } = new MotionScene(script, art, "1");
  for (const z of [0, 80 / 3, 160 / 3]) {
    const [x, , pixelsPerYard] = camera.project(40, 0, z);
    const [nextX] = camera.project(50, 0, z);
    expect((nextX - x) / pixelsPerYard).toBeCloseTo(10, 9);
  }
});
