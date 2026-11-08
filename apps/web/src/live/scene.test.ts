import { expect, it } from "vitest";
import { type Art, Scene, type Script } from "./scene";

const art = {
  meta: { camera: { x: 50, rise: 20, back: 70, look: [0, 20] } },
} as Art;

it("preserves the terminal ball after the scene ends while the Jumbotron continues", () => {
  const makeScene = (ball: Script["ball"]) =>
    new Scene({ duration: 3, actors: [], ball } as unknown as Script, art, "home");
  const held = makeScene([{ start: 0, end: 3, state: "held", actor: "runner", spin: "flat" }]);
  const resting = makeScene([{ start: 0, end: 3, state: "rest", at: [80, 0, 20], spin: "flat" }]);
  expect(held.carrier(3)).toBe("runner");
  expect(held.carrier(4)).toBe("runner");
  expect(resting.ball(4)?.at).toEqual([80, 0, 20]);
});
