import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { FrontOffice } from "./FrontOffice";

vi.mock("./session", () => ({
  useSession: () => ({
    me: { observer: false, current_team_id: "own", teams: [], preferences: { watchlist: [] } },
  }),
}));
vi.mock("./events", () => ({ useFallbackInterval: () => false }));
afterEach(() => vi.unstubAllGlobals());

const team = (id: string, name: string, managers: string[]) => ({
  id,
  name,
  abbreviation: id.toUpperCase().slice(0, 3),
  wins: 5,
  losses: 3,
  ties: 0,
  points_for: "1000.00",
  points_against: "900.00",
  waiver_rank: 6,
  playoff_seed: 2,
  managers,
  transactions: null,
});
const rules = {
  lineup_slots: ["QB", "BENCH"],
  waiver_type: "WAIVERS_TRADITIONAL",
  waiver_hours: 24,
  waiver_days: [],
  uses_bidding: false,
  trade_deadline: null,
  trade_veto_votes: null,
  trade_review_hours: null,
  regular_season_matchups: 14,
  playoff_team_count: null,
  playoff_tiebreaker: null,
};

function office(changes: Record<string, unknown>) {
  return {
    snapshot: {
      id: "snap",
      observed_at: "2026-11-08T00:00:00Z",
      confirmed_at: "2026-11-08T00:00:00Z",
      source_status: "fresh",
      stale: false,
      season: 2026,
      scoring_period: 9,
      matchup_period: 9,
    },
    team: team("own", "Fictional Own", ["Avery"]),
    matchup: null,
    roster: [],
    roster_state: "current",
    lineup: [],
    lineup_captured_at: null,
    standings: [team("own", "Fictional Own", ["Avery"]), team("rival", "Fictional Rival", [])],
    analysis: { status: "unavailable", reason: "" },
    matchup_periods: [8, 9, 10],
    selected_matchup_period: 9,
    season_strip: [],
    league: rules,
    recent_moves: [],
    fixture: true,
    ...changes,
  };
}

async function show(body: object) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      Response.json(url.includes("sources") ? { sources: [] } : body, { status: 200 }),
    ),
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <FrontOffice />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return screen.findByRole("region", { name: /Matchup/ });
}

const side = (id: string, official: string | null, live: string | null) => ({
  team_id: id,
  official_points: official,
  live_points: live,
});

it("labels a running total Live and never as official, and leaves a side that hasn't played blank", async () => {
  const board = await show(
    office({
      matchup: {
        id: "m9",
        matchup_period: 9,
        scoring_periods: [9],
        home: side("own", null, "64.3"),
        away: side("rival", null, null),
        winner: null,
        playoff_tier: "NONE",
      },
    }),
  );
  expect(within(board).getByText("Live")).toBeTruthy();
  expect(within(board).queryByText("Official")).toBeNull();
  expect(within(board).getByText("64.30")).toBeTruthy();
  expect(within(board).getByText("Score unavailable")).toBeTruthy();
  expect(within(board).getByText(/Avery/)).toBeTruthy();
});

it("shows ESPN's official total for a decided week and that week's stored lineup", async () => {
  const board = await show(
    office({
      selected_matchup_period: 8,
      roster_state: "lineup",
      lineup_captured_at: "2026-11-08T01:00:00Z",
      lineup: [
        {
          player_id: "p1",
          display_name: "Fictional Passer",
          position: "QB",
          slot: "QB",
          official_points: "21.5",
        },
      ],
      matchup: {
        id: "m8",
        matchup_period: 8,
        scoring_periods: [8],
        home: side("own", "140.46", null),
        away: side("rival", "90.3", null),
        winner: "home",
        playoff_tier: "NONE",
      },
    }),
  );
  expect(within(board).getByText("Official")).toBeTruthy();
  expect(within(board).getByText("Final")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Lineup, matchup 8" })).toBeTruthy();
  expect(screen.getByText("Fictional Passer")).toBeTruthy();
  expect(screen.getByText("21.50")).toBeTruthy();
});

it("says a future week hasn't been played rather than showing zeros", async () => {
  const board = await show(
    office({
      selected_matchup_period: 10,
      roster_state: "not_played",
      matchup: {
        id: "m10",
        matchup_period: 10,
        scoring_periods: [10],
        home: side("own", null, null),
        away: side("rival", null, null),
        winner: null,
        playoff_tier: "NONE",
      },
    }),
  );
  expect(within(board).getByText("Not started")).toBeTruthy();
  expect(within(board).queryByText("0.00")).toBeNull();
  expect(screen.getByText("Matchup 10 hasn’t been played yet")).toBeTruthy();
});
