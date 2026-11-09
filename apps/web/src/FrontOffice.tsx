import { useQuery } from "@tanstack/react-query";
import { Fragment, useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import type {
  LeagueRules,
  LineupPlayer,
  MatchupSide,
  FrontOffice as Office,
  Player,
  RecentMove,
  Sources,
  Team,
} from "./api";
import { useFallbackInterval } from "./events";
import { ageLabel, dateLabel, injuryLabel, injuryRulesOut, points, record } from "./format";
import { Arrow, Busy, Notice, PageTitle, StatePanel } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";
import { setViewingTeam, useViewingTeam } from "./viewing";

const GROUPS = [
  { key: "starters", title: "Starters" },
  { key: "bench", title: "Bench" },
  { key: "reserve", title: "Injured reserve" },
] as const;
function groupOf(slot: string | null) {
  if (slot === "BENCH") return "bench";
  if (slot === "IR") return "reserve";
  return "starters";
}

/** ESPN's official total once it has decided the week; otherwise its running total, labeled. */
function shown(side: MatchupSide | null | undefined) {
  if (side?.official_points != null) return { value: side.official_points, live: false };
  if (side?.live_points != null) return { value: side.live_points, live: true };
  return { value: null, live: false };
}

export function FrontOffice() {
  const [params, setParams] = useSearchParams();
  const { me } = useSession();
  const requestedTeam = params.get("team");
  const period = params.get("period");
  const viewing = useViewingTeam();
  const teamId = requestedTeam ?? (me?.observer ? viewing : null) ?? me?.current_team_id;
  useEffect(() => {
    // The dev account remembers the team it's viewing, so Live shows that manager's players.
    if (me?.observer && teamId && teamId !== viewing) setViewingTeam(teamId);
  }, [me?.observer, teamId, viewing]);
  const search = new URLSearchParams();
  if (teamId) search.set("team_id", teamId);
  if (period) search.set("matchup_period", period);
  const query = useQuery({
    queryKey: ["front-office", teamId, period],
    queryFn: ({ signal }) => http<Office>(`/api/v1/front-office?${search}`, { signal }),
    refetchInterval: useFallbackInterval(),
  });
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };
  if (query.isPending) return <Busy />;
  if (!query.data)
    return (
      <StatePanel title="League data unavailable">
        <p>Your team’s data couldn’t be loaded. Your account and preferences are unaffected.</p>
        <div className="actions">
          <button className="primary" type="button" onClick={() => void query.refetch()}>
            Retry
          </button>
          <Link className="link-button" to="/front-office">
            Your team
          </Link>
        </div>
      </StatePanel>
    );
  const data = query.data;
  const position = params.get("position") ?? "";
  const watchOnly = params.get("watched") === "true";
  const roster = data.roster.filter(
    (player) =>
      (!position || player.position === position) &&
      (!watchOnly || me?.preferences.watchlist.includes(player.id)),
  );
  const own =
    data.matchup?.home?.team_id === data.team.id
      ? data.matchup.home
      : data.matchup?.away?.team_id === data.team.id
        ? data.matchup.away
        : null;
  const other =
    data.matchup?.home?.team_id === data.team.id
      ? data.matchup.away
      : data.matchup?.away?.team_id === data.team.id
        ? data.matchup.home
        : null;
  const opponent = data.standings.find((team) => team.id === other?.team_id);
  const ownScore = shown(own);
  const otherScore = shown(other);
  const scored = ownScore.value != null && otherScore.value != null;
  const ownTrails = scored && Number(ownScore.value) < Number(otherScore.value);
  const otherTrails = scored && Number(otherScore.value) < Number(ownScore.value);
  const live = ownScore.live || otherScore.live;
  const official = !live && (ownScore.value != null || otherScore.value != null);
  const selected = data.selected_matchup_period;
  const current = data.snapshot.matchup_period;
  const state = data.matchup?.winner
    ? "Final"
    : selected === current
      ? "In progress"
      : selected > current
        ? "Not started"
        : "Awaiting ESPN’s final";
  function openPlayer(id: string) {
    const next = new URLSearchParams(params);
    next.set("player", id);
    next.set("player_snapshot", data.snapshot.id);
    setParams(next);
  }
  return (
    <>
      <PageTitle title="Front Office">
        {me && me.teams.length > 1 && (
          <div className="context-controls">
            <label>
              Team
              <select value={data.team.id} onChange={(event) => set("team", event.target.value)}>
                {me.teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </PageTitle>
      {query.isError && (
        <Notice
          danger
          action={
            <button type="button" onClick={() => void query.refetch()}>
              Retry
            </button>
          }
        >
          Refresh failed. Showing the last saved data.
        </Notice>
      )}
      {!query.isError && (data.snapshot.stale || data.snapshot.source_status !== "fresh") && (
        <Notice>This data is behind ESPN. Scores, ownership and locks may have changed.</Notice>
      )}
      <section className="score-board" aria-labelledby="matchup-heading">
        <div className="score-head">
          <div className="score-title">
            <h2 id="matchup-heading">Matchup {selected}</h2>
            {official && <span className="authority">Official</span>}
            {live && (
              <span className="authority" data-kind="live">
                Live
              </span>
            )}
            <span>{state}</span>
          </div>
          <a
            href="https://fantasy.espn.com/football/league?leagueId=1729878439"
            target="_blank"
            rel="noopener noreferrer"
          >
            Open in ESPN <Arrow direction="up" />
          </a>
        </div>
        <div className="score-sides">
          <ScoreTeam team={data.team} score={ownScore.value} own trailing={ownTrails} />
          <ScoreTeam team={opponent} score={otherScore.value} trailing={otherTrails} />
        </div>
        <nav aria-label="Matchups this season">
          <ol className="season-strip">
            {data.season_strip.map((cell) => {
              const next = new URLSearchParams(params);
              if (cell.matchup_period === data.snapshot.matchup_period) next.delete("period");
              else next.set("period", String(cell.matchup_period));
              const label = cell.result ? { win: "W", loss: "L", tie: "T" }[cell.result] : "–";
              return (
                <li key={cell.matchup_period}>
                  <Link
                    to={`?${next}`}
                    data-result={cell.result ?? undefined}
                    data-current={cell.matchup_period === data.snapshot.matchup_period}
                    aria-current={
                      cell.matchup_period === data.selected_matchup_period ? "true" : undefined
                    }
                    aria-label={`Matchup ${cell.matchup_period}${cell.result ? `, ${cell.result}` : ""}${
                      cell.matchup_period === data.snapshot.matchup_period ? ", current" : ""
                    }`}
                  >
                    <b>{cell.matchup_period}</b>
                    <small>{label}</small>
                  </Link>
                </li>
              );
            })}
          </ol>
        </nav>
        {live && (
          <p className="score-note">
            Live totals from ESPN. The official score comes when ESPN closes the week.
          </p>
        )}
      </section>
      <div className="office-grid">
        <section aria-labelledby="roster-heading">
          <div className="section-head">
            <h2 id="roster-heading">
              {data.roster_state === "current" ? "Roster" : `Lineup, matchup ${selected}`}
            </h2>
            {data.roster_state === "current" && (
              <div className="section-tools">
                <label htmlFor="roster-position">Position</label>
                <select
                  id="roster-position"
                  value={position}
                  onChange={(event) => set("position", event.target.value)}
                >
                  <option value="">All</option>
                  {["QB", "RB", "WR", "TE", "K", "DST"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="toggle"
                  aria-pressed={watchOnly}
                  onClick={() => set("watched", watchOnly ? "" : "true")}
                >
                  Watchlist
                </button>
              </div>
            )}
          </div>
          {data.roster_state === "lineup" ? (
            <LineupTable
              lineup={data.lineup}
              period={selected}
              capturedAt={data.lineup_captured_at}
            />
          ) : data.roster_state !== "current" ? (
            <div className="inline-state">
              <h3>
                {data.roster_state === "not_played"
                  ? `Matchup ${selected} hasn’t been played yet`
                  : "This week’s lineup isn’t stored yet"}
              </h3>
              <p>
                {data.roster_state === "not_played"
                  ? "Lineups and scores appear here once the week is over."
                  : "Finished weeks are read from ESPN one at a time. The score above is ESPN’s."}
              </p>
              <button type="button" onClick={() => set("period", "")}>
                Current roster
              </button>
            </div>
          ) : roster.length ? (
            <div className="table-wrap">
              <table className="agate roster-table">
                <caption className="sr-only">
                  Roster for scoring period {data.snapshot.scoring_period}, official ESPN points.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Slot</th>
                    <th scope="col">Player</th>
                    <th scope="col" className="player-status-heading">
                      Status
                    </th>
                    <th scope="col" className="numeric">
                      Pts
                    </th>
                    <th scope="col" className="numeric season-cell">
                      <abbr title="Official ESPN points this season">Season</abbr>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {GROUPS.map((group) => {
                    const rows = roster.filter(
                      (player) => groupOf(player.lineup_slot) === group.key,
                    );
                    if (!rows.length) return null;
                    return (
                      <Fragment key={group.key}>
                        <tr className="group-row">
                          <th colSpan={5} scope="colgroup">
                            {group.title}
                          </th>
                        </tr>
                        {rows.map((player) => (
                          <RosterRow
                            key={player.id}
                            player={player}
                            watched={!!me?.preferences.watchlist.includes(player.id)}
                            open={() => openPlayer(player.id)}
                          />
                        ))}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="inline-state">
              <p>
                {data.roster.length === 0
                  ? "No roster data in this saved league view."
                  : "No players match these filters."}
              </p>
              {data.roster.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.delete("position");
                    next.delete("watched");
                    setParams(next);
                  }}
                >
                  Clear filters
                </button>
              )}
            </div>
          )}
        </section>
        <aside className="office-rail" aria-label="League">
          <section aria-labelledby="standings-heading">
            <div className="section-head">
              <h2 id="standings-heading">League table</h2>
            </div>
            <div className="table-wrap">
              <table className="agate standings-table">
                <caption className="sr-only">
                  Current standings in reported playoff seed order.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Team</th>
                    <th scope="col" className="numeric">
                      W–L–T
                    </th>
                    <th scope="col" className="numeric">
                      <abbr title="Points for">PF</abbr>
                    </th>
                    <th scope="col" className="numeric">
                      <abbr title="Reported playoff seed">Seed</abbr>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.standings.map((team, index) => (
                    <Fragment key={team.id}>
                      <tr className={team.id === data.team.id ? "own-standing" : ""}>
                        <th scope="row">
                          {team.name}
                          {team.id === data.team.id && (
                            <span className="sr-only"> (your team)</span>
                          )}
                          {team.managers.length > 0 && (
                            <span className="team-managers">{team.managers.join(", ")}</span>
                          )}
                        </th>
                        <td className="numeric">{record(team)}</td>
                        <td className="numeric">{points(team.points_for)}</td>
                        <td className="numeric">{team.playoff_seed ?? "—"}</td>
                      </tr>
                      {data.league.playoff_team_count != null &&
                        index + 1 === data.league.playoff_team_count &&
                        index + 1 < data.standings.length && (
                          <tr className="playoff-line">
                            <td colSpan={4}>
                              <span>Playoff line</span>
                            </td>
                          </tr>
                        )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <LeaguePanel rules={data.league} team={data.team} teams={data.standings.length} />
          <MovesPanel moves={data.recent_moves} />
          <SourcePanel />
          <section className="fact-panel" aria-labelledby="recommendations-heading">
            <h2 id="recommendations-heading">Recommendations</h2>
            <span className="state-off">Off</span>
            <p className="fine">
              Lineup, waiver and trade calls need player projections, which aren’t built yet.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}

function gameLine(nfl: NonNullable<Player["nfl"]>): string {
  if (nfl.on_bye) return "Bye";
  if (!nfl.opponent_abbreviation) return "No game listed";
  const when = nfl.kickoff
    ? new Intl.DateTimeFormat(undefined, {
        weekday: "short",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(nfl.kickoff))
    : "";
  return `${nfl.home ? "vs" : "at"} ${nfl.opponent_abbreviation}${when ? ` ${when}` : ""}`;
}

const SOURCE_STATE: Record<Sources["sources"][number]["state"], string> = {
  current: "Current",
  behind: "Behind",
  down: "Failing",
  idle: "No games on",
  never: "Not read yet",
};

function SourcePanel() {
  const query = useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => http<Sources>("/api/v1/sources", { signal }),
    refetchInterval: 60_000,
  });
  if (!query.data) return null;
  return (
    <section className="fact-panel" aria-labelledby="sources-heading">
      <h2 id="sources-heading">Data</h2>
      <ul className="source-list">
        {query.data.sources.map((row) => (
          <li key={row.source}>
            <span>{row.label}</span>
            <span
              className="status"
              data-state={
                row.state === "down"
                  ? "down"
                  : row.state === "behind" || row.state === "never"
                    ? "behind"
                    : "current"
              }
            >
              <span>
                {SOURCE_STATE[row.state]}
                {row.last_success_at && row.state !== "idle" ? (
                  <>
                    {" · "}
                    <time dateTime={row.last_success_at} title={dateLabel(row.last_success_at)}>
                      {ageLabel(row.last_success_at)}
                    </time>
                  </>
                ) : null}
                {row.error_code ? ` · ${row.error_code}` : ""}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RosterRow({
  player,
  watched,
  open,
}: {
  player: Player;
  watched: boolean;
  open: () => void;
}) {
  const status = injuryLabel(player.injury) ?? (!player.active ? "Inactive" : null);
  return (
    <tr>
      <td className="slot-cell">
        <span className="slot-tag">{player.lineup_slot ?? "—"}</span>
      </td>
      <td className="player-cell">
        <button type="button" className="player-link" onClick={open}>
          {player.display_name}
          {watched && (
            <span role="img" aria-label="On watchlist" className="watched">
              W
            </span>
          )}
        </button>
        <span className="player-line">
          {player.position}
          {player.nfl ? ` · ${player.nfl.team_abbreviation}` : ""}
          {player.nfl ? ` · ${gameLine(player.nfl)}` : ""}
          <span className="mobile-status">{status ? ` · ${status}` : ""}</span>
          {player.lineup_locked ? <span className="mobile-status"> · Locked</span> : null}
        </span>
      </td>
      <td className="player-status">
        {status ? (
          <span
            className={`tag ${injuryRulesOut(player.injury) || !player.active ? "tag-fault" : "tag-caution"}`}
          >
            {status}
          </span>
        ) : (
          <span className="muted">—</span>
        )}
        {player.lineup_locked && <span className="tag tag-lock">Locked</span>}
      </td>
      <td className="numeric score-cell">
        {points(player.official_current_points)}
        {player.official_current_points === null && (
          <span className="sr-only"> Score unavailable</span>
        )}
      </td>
      <td className="numeric season-cell">{points(player.official_season_points)}</td>
    </tr>
  );
}

function LineupTable({
  lineup,
  period,
  capturedAt,
}: {
  lineup: LineupPlayer[];
  period: number;
  capturedAt: string | null | undefined;
}) {
  return (
    <div className="table-wrap">
      <table className="agate roster-table">
        <caption className="sr-only">
          Lineup for matchup {period}, official ESPN points that week.
        </caption>
        <thead>
          <tr>
            <th scope="col">Slot</th>
            <th scope="col">Player</th>
            <th scope="col" className="numeric">
              Pts
            </th>
          </tr>
        </thead>
        <tbody>
          {GROUPS.map((group) => {
            const rows = lineup.filter((entry) => groupOf(entry.slot) === group.key);
            if (!rows.length) return null;
            return (
              <Fragment key={group.key}>
                <tr className="group-row">
                  <th colSpan={3} scope="colgroup">
                    {group.title}
                  </th>
                </tr>
                {rows.map((entry) => (
                  <tr key={entry.player_id}>
                    <td className="slot-cell">
                      <span className="slot-tag">{entry.slot}</span>
                    </td>
                    <td className="player-cell">
                      <span className="player-name">{entry.display_name}</span>
                      <span className="player-line">{entry.position}</span>
                    </td>
                    <td className="numeric score-cell">
                      {points(entry.official_points)}
                      {entry.official_points == null && (
                        <span className="sr-only"> Did not play</span>
                      )}
                    </td>
                  </tr>
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      {capturedAt && (
        <p className="table-foot">
          Slots and points as ESPN recorded them that week, read{" "}
          <time dateTime={capturedAt}>{dateLabel(capturedAt)}</time>.
        </p>
      )}
    </div>
  );
}

const WAIVER_TYPES: Record<string, string> = { WAIVERS_TRADITIONAL: "Traditional waivers" };
const TIEBREAKERS: Record<string, string> = {
  TOTAL_POINTS_SCORED: "total points",
  H2H_RECORD: "head-to-head record",
  TOTAL_POINTS_AGAINST: "points against",
  INTRA_DIVISION_RECORD: "division record",
};
const DAYS: Record<string, string> = {
  MONDAY: "Mon",
  TUESDAY: "Tue",
  WEDNESDAY: "Wed",
  THURSDAY: "Thu",
  FRIDAY: "Fri",
  SATURDAY: "Sat",
  SUNDAY: "Sun",
};

function untilLabel(when: string, now = Date.now()): string {
  const days = Math.ceil((Date.parse(when) - now) / 86_400_000);
  if (!Number.isFinite(days)) return "";
  if (days < 0) return "passed";
  if (days === 0) return "today";
  return days === 1 ? "in 1 day" : `in ${days} days`;
}

function LeaguePanel({ rules, team, teams }: { rules: LeagueRules; team: Team; teams: number }) {
  const waiver = [
    rules.waiver_type ? (WAIVER_TYPES[rules.waiver_type] ?? "Waivers") : null,
    rules.waiver_hours != null ? `${rules.waiver_hours}-hour hold` : null,
    rules.uses_bidding === false ? "no bidding" : null,
  ].filter(Boolean);
  const moves = team.transactions;
  return (
    <section className="fact-panel" aria-labelledby="league-heading">
      <h2 id="league-heading">League</h2>
      <dl className="fact-list">
        <div>
          <dt>Your waiver priority</dt>
          <dd>{team.waiver_rank != null ? `${team.waiver_rank} of ${teams}` : "—"}</dd>
        </div>
        <div>
          <dt>Waivers</dt>
          <dd>{waiver.length ? waiver.join(", ") : "—"}</dd>
        </div>
        {rules.waiver_days.length > 0 && (
          <div>
            <dt>Claims processed</dt>
            <dd>{rules.waiver_days.map((day) => DAYS[day] ?? day).join(", ")}</dd>
          </div>
        )}
        <div>
          <dt>Trade deadline</dt>
          <dd>
            {rules.trade_deadline ? (
              <>
                <time dateTime={rules.trade_deadline}>{dateLabel(rules.trade_deadline)}</time>
                <span className="fine"> {untilLabel(rules.trade_deadline)}</span>
              </>
            ) : (
              "—"
            )}
          </dd>
        </div>
        {rules.trade_veto_votes != null && (
          <div>
            <dt>Votes to veto a trade</dt>
            <dd>{rules.trade_veto_votes}</dd>
          </div>
        )}
        {rules.playoff_team_count != null && (
          <div>
            <dt>Playoffs</dt>
            <dd>
              {rules.playoff_team_count} teams
              {rules.playoff_tiebreaker && TIEBREAKERS[rules.playoff_tiebreaker]
                ? `, ties broken by ${TIEBREAKERS[rules.playoff_tiebreaker]}`
                : ""}
            </dd>
          </div>
        )}
        {moves && (
          <div>
            <dt>Your moves this season</dt>
            <dd>
              {moves.acquisitions} adds, {moves.drops} drops, {moves.trades} trades
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}

const MOVE_KINDS: Record<RecentMove["kind"], string> = {
  waiver: "Waiver claim",
  free_agent: "Free agent",
  trade: "Trade",
  other: "Roster move",
};

function MovesPanel({ moves }: { moves: RecentMove[] }) {
  return (
    <section className="fact-panel" aria-labelledby="moves-heading">
      <h2 id="moves-heading">Recent moves</h2>
      {moves.length ? (
        <ul className="move-list">
          {moves.map((move) => (
            <li key={move.id}>
              <p>
                {move.kind !== "trade" && <b>{move.team_name ?? "A team"} </b>}
                {move.items
                  .map((item) =>
                    item.action === "traded"
                      ? `${item.player_name ?? "a player no longer listed"} to ${item.team_name ?? "another team"}`
                      : `${item.action} ${item.player_name ?? "a player no longer listed"}`,
                  )
                  .join(", ")}
              </p>
              <p className="fine">
                {MOVE_KINDS[move.kind]}
                {move.at ? (
                  <>
                    {" · "}
                    <time dateTime={move.at} title={dateLabel(move.at)}>
                      {ageLabel(move.at)}
                    </time>
                  </>
                ) : null}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="fine">No adds, drops or trades read from ESPN yet.</p>
      )}
    </section>
  );
}

function ScoreTeam({
  team,
  score,
  own = false,
  trailing = false,
}: {
  team?: Team;
  score?: string | null;
  own?: boolean;
  trailing?: boolean;
}) {
  return (
    <div className={`score-team ${own ? "own-team" : ""}`}>
      <div className="team-tile" aria-hidden="true">
        {team?.abbreviation || "?"}
      </div>
      <div className="team-id">
        <h3>{team?.name ?? "Opponent unavailable"}</h3>
        <p>
          {own ? "Your team · " : ""}
          {team?.managers.length ? `${team.managers.join(", ")} · ` : ""}
          {team ? record(team) : "Record unavailable"}
          {team?.playoff_seed != null ? ` · Seed ${team.playoff_seed}` : ""}
        </p>
      </div>
      <p className="matchup-score" data-trailing={trailing} data-unknown={score == null}>
        {points(score)}
        {score == null && <span className="sr-only"> Score unavailable</span>}
      </p>
    </div>
  );
}
