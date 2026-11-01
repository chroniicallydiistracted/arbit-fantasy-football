import { describe, expect, it } from "vitest";
import { ageLabel, points, record } from "./format";

describe("official fact presentation", () => {
  it("distinguishes an unknown score from an actual zero without rounding exact totals", () => {
    expect(points(null)).toBe("—");
    expect(points("0")).toBe("0.00");
    expect(points("112.345")).toBe("112.345");
    expect(points("-2.5")).toBe("-2.50");
  });
  it("keeps ties in a team's official record", () => {
    expect(record({ wins: 3, losses: 4, ties: 1 })).toBe("3–4–1");
  });
  it("never claims future or invalid source times are fresh", () => {
    const now = Date.parse("2026-10-31T12:00:00Z");
    expect(ageLabel("2026-10-31T11:58:00Z", now)).toBe("2 min ago");
    expect(ageLabel("2026-11-01T00:00:00Z", now)).toBe("time unknown");
    expect(ageLabel("invalid", now)).toBe("time unknown");
  });
});
