import { useQuery } from "@tanstack/react-query";
import { Fragment, useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import type { FrontOffice as Office, Player, Sources, Team } from "./api";
import { useFallbackInterval } from "./events";
import { ageLabel, dateLabel, points, record } from "./format";
import { Arrow, Busy, Notice, PageTitle, StatePanel } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";
import { setViewingTeam, useViewingTeam } from "./viewing";

const GROUPS = [
  { key: "starters", title: "Starters" },
  { key: "bench", title: "Bench" },
  { key: "reserve", title: "Injured reserve" },
] as const;
function groupOf(player: Player) {
  if (player.lineup_slot === "BENCH") return "bench";
  if (player.lineup_slot === "IR") return "reserve";
  return "starters";
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
  const scored = own?.official_points != null && other?.official_points != null;
  const ownTrails = scored && Number(own.official_points) < Number(other.official_points);
  const otherTrails = scored && Number(other.official_points) < Number(own.official_points);
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
            <h2 id="matchup-heading">Matchup {data.selected_matchup_period}</h2>
            <span className="authority">Official</span>
            <span>
              {data.selected_matchup_period < data.snapshot.matchup_period
                ? "Final"
                : data.selected_matchup_period === data.snapshot.matchup_period
                  ? "In progress"
                  : "Not started"}
            </span>
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
          <ScoreTeam team={data.team} score={own?.official_points} own trailing={ownTrails} />
          <ScoreTeam team={opponent} score={other?.official_points} trailing={otherTrails} />
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
      </section>
      <div className="office-grid">
        <section aria-labelledby="roster-heading">
          <div className="section-head">
            <h2 id="roster-heading">
              {data.historical_roster_unavailable
                ? `Roster, matchup ${data.selected_matchup_period}`
                : "Roster"}
            </h2>
            {!data.historical_roster_unavailable && (
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
          {data.historical_roster_unavailable ? (
            <div className="inline-state">
              <h3>No roster saved for this matchup</h3>
              <p>The score above is the official total. Today’s roster isn’t shown in its place.</p>
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
                  </tr>
                </thead>
                <tbody>
                  {GROUPS.map((group) => {
                    const rows = roster.filter((player) => groupOf(player) === group.key);
                    if (!rows.length) return null;
                    return (
                      <Fragment key={group.key}>
                        <tr className="group-row">
                          <th colSpan={4} scope="colgroup">
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
                        </th>
                        <td className="numeric">{record(team)}</td>
                        <td className="numeric">{points(team.points_for)}</td>
                        <td className="numeric">{team.playoff_seed ?? "—"}</td>
                      </tr>
                      {data.playoff_team_count != null &&
                        index + 1 === data.playoff_team_count &&
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
  const injury =
    player.injury_status && player.injury_status !== "ACTIVE" ? player.injury_status : null;
  const status = injury ?? (player.injured ? "Injured" : !player.active ? "Inactive" : null);
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
            className={`tag ${status === "OUT" || status === "Inactive" ? "tag-fault" : "tag-caution"}`}
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
    </tr>
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
