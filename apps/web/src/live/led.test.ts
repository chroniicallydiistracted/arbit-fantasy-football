import { expect, it } from "vitest";
import { runningClock } from "./led";

const SNAP = 0.6;

it("runs the game clock one second per second from the snap and holds on the play's end clock", () => {
  // A four-second play: 10:00 at the snap, 9:56 at the whistle (OWN-051).
  expect(runningClock("10:00", "9:56", 0.3)).toBe("10:00");
  expect(runningClock("10:00", "9:56", SNAP + 1.0)).toBe("9:59");
  expect(runningClock("10:00", "9:56", SNAP + 2.5)).toBe("9:58");
  expect(runningClock("10:00", "9:56", SNAP + 4.0)).toBe("9:56");
  // The re-creation may finish after the real whistle: the clock has already stopped.
  expect(runningClock("10:00", "9:56", SNAP + 6.5)).toBe("9:56");
});

it("keeps the snap clock when the play's end clock is unknown or the clock didn't run", () => {
  expect(runningClock("0:42", null, SNAP + 2)).toBe("0:42");
  expect(runningClock("0:42", "0:42", SNAP + 2)).toBe("0:42");
  expect(runningClock(null, "0:40", SNAP + 2)).toBe(null);
});
