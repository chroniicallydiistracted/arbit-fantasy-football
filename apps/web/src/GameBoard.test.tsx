import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { FieldStrip, type Game, GameBoard, trailing } from "./GameBoard";

const team = (abbreviation: string, score: string | null, overrides = {}) => ({
  abbreviation,
  name: `${abbreviation} team`,
  score,
  color: "112233",
  record: "3-4",
  periods: [],
  timeouts: null,
  has_ball: false,
  ...overrides,
});

const live: NonNullable<Game["situation"]> = {
  down: 1,
  distance: 10,
  short_text: "1st & 10",
  field_text: "AWY 20",
  yard_line: 80,
  first_down_line: 70,
  possession: "away",
  red_zone: false,
  last_play: { kind: "Rush", text: " Runner for 3 yards.", yards: 3 },
};

const game = (overrides: Partial<Game> = {}): Game => ({
  event_id: "1",
  phase: "in_progress",
  kickoff: null,
  period: 4,
  clock: "9:38",
  home: team("HOM", "24", { periods: ["3", "7", "14", "0"], timeouts: 3 }),
  away: team("AWY", "17", { periods: ["0", "3", "7", "7"], timeouts: 2, has_ball: true }),
  situation: live,
  venue: { name: "Test Field", city: "Testville", state: "TS", indoor: false },
  weather: { temperature: 69, condition: "Sunny" },
  broadcast: ["Fox"],
  own_players: [],
  observed_at: "2026-11-01T22:00:00Z",
  changed_at: "2026-11-01T22:00:00Z",
  ...overrides,
});

it("places the ball and first-down line from the home goal line, away team on the left", () => {
  const { container } = render(<FieldStrip game={game()} />);
  expect(
    screen.getByRole("img", { name: /Ball at AWY 20. AWY driving toward the right/ }),
  ).toBeTruthy();
  expect((container.querySelector(".fs-los") as HTMLElement).style.left).toBe("20%");
  expect((container.querySelector(".fs-first") as HTMLElement).style.left).toBe("30%");
});

it("points the home team's drive the other way", () => {
  const home = game({
    situation: { ...live, possession: "home", yard_line: 44, first_down_line: 50 },
  });
  const { container } = render(<FieldStrip game={home} />);
  expect((container.querySelector(".fs-ball") as HTMLElement).dataset.toward).toBe("left");
  expect((container.querySelector(".fs-los") as HTMLElement).style.left).toBe("56%");
});

it("shows nothing on the field when ESPN has given no spot", () => {
  const { container } = render(
    <FieldStrip game={game({ situation: { ...live, yard_line: null } })} />,
  );
  expect(container.firstChild).toBeNull();
});

it("shows the live state and every quarter", () => {
  render(<GameBoard game={game()} />);
  expect(screen.getByRole("heading", { name: "AWY at HOM" })).toBeTruthy();
  expect(screen.getByText("1st & 10")).toBeTruthy();
  expect(screen.getByRole("table", { name: "Score by quarter" }).textContent).toContain("Q4");
  expect(screen.getByRole("img", { name: "3 timeouts left" })).toBeTruthy();
});

it("doesn't repeat a last play label that differs from ESPN's text only in capitals", () => {
  const last_play = { kind: "Two-minute warning", text: "Two-Minute Warning", yards: null };
  const { container } = render(<GameBoard game={game({ situation: { ...live, last_play } })} />);
  expect(container.textContent?.match(/two-minute warning/gi)).toHaveLength(1);
});

it("keeps an unplayed game's score unknown rather than zero", () => {
  render(
    <GameBoard
      game={game({
        phase: "scheduled",
        kickoff: "2026-11-02T01:20:00Z",
        period: null,
        clock: null,
        situation: null,
        home: team("HOM", null),
        away: team("AWY", null),
      })}
    />,
  );
  expect(screen.queryByRole("table", { name: "Score by quarter" })).toBeNull();
  expect(screen.getAllByText("—")).toHaveLength(2);
  const announced = screen.getByRole("status").textContent ?? "";
  expect(announced).toContain("AWY at HOM.");
  expect(announced).not.toContain("unknown");
  expect(trailing(game({ phase: "scheduled" }), team("A", null), team("B", null))).toBe(false);
});
