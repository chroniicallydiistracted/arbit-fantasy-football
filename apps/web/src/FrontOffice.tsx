import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import type { FrontOffice as Office, Team } from "./api";
import { points, record } from "./format";
import { Arrow, Busy, Empty, Notice, SourceNote } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";

export function FrontOffice() {
  const [params, setParams] = useSearchParams();
  const { me } = useSession();
  const requestedTeam = params.get("team");
  const period = params.get("period");
  const teamId = requestedTeam ?? me?.current_team_id;
  const search = new URLSearchParams();
  if (teamId) search.set("team_id", teamId);
  if (period) search.set("matchup_period", period);
  const query = useQuery({
    queryKey: ["front-office", teamId, period],
    queryFn: ({ signal }) => http<Office>(`/api/v1/front-office?${search}`, { signal }),
    refetchInterval: 60_000,
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
      <Empty eyebrow="Front Office" title="The league view is unavailable.">
        <p>
          Your team details could not be loaded. Your account and saved preferences are still here.
        </p>
        <button className="primary" type="button" onClick={() => void query.refetch()}>
          Try again <Arrow />
        </button>
        <Link className="text-link" to="/front-office">
          Return to your team
        </Link>
      </Empty>
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
  function openPlayer(id: string) {
    const next = new URLSearchParams(params);
    next.set("player", id);
    next.set("player_snapshot", data.snapshot.id);
    setParams(next);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">FFA / {data.snapshot.season} season</p>
          <h1>
            Front Office<span className="heading-period">.</span>
          </h1>
        </div>
        <div className="context-controls">
          {me && me.teams.length > 1 && (
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
          )}
          <label>
            Fantasy matchup
            <select
              value={data.selected_matchup_period}
              onChange={(event) => set("period", event.target.value)}
            >
              {data.matchup_periods.map((value) => (
                <option key={value} value={value}>
                  Matchup {value}
                  {value === data.snapshot.matchup_period ? " · Current" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {query.isError && (
        <Notice
          danger
          action={
            <button type="button" onClick={() => void query.refetch()}>
              Retry
            </button>
          }
        >
          Refresh failed. These are the previously saved facts, observed at the time below.
        </Notice>
      )}
      <SourceNote snapshot={data.snapshot} failed={query.isError} />
      {(data.snapshot.stale || data.snapshot.source_status !== "fresh") && (
        <p className="stale-explanation">
          This saved league view may be out of date. Scores, ownership and locks may have changed in
          ESPN.
        </p>
      )}
      <div className="office-grid">
        <div className="office-main">
          <section className="matchup-panel" aria-labelledby="matchup-heading">
            <div className="section-kicker">
              <h2 id="matchup-heading">Matchup {data.selected_matchup_period}</h2>
              <span>Official ESPN totals</span>
            </div>
            <div className="matchup-teams">
              <ScoreTeam team={data.team} score={own?.official_points} own />
              <span className="versus">vs</span>
              <ScoreTeam team={opponent} score={other?.official_points} />
            </div>
            <div className="matchup-foot">
              <span>
                {own?.official_points == null || other?.official_points == null
                  ? "A score is not yet available. Unknown totals are shown as —."
                  : "Official fantasy points · No projected points added"}
              </span>
              <a
                href="https://fantasy.espn.com/football/league?leagueId=1729878439"
                target="_blank"
                rel="noopener noreferrer"
              >
                View league in ESPN <Arrow direction="up" />
              </a>
            </div>
          </section>
          <section className="roster-section" aria-labelledby="roster-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">The team sheet</p>
                <h2 id="roster-heading">
                  {data.historical_roster_unavailable ? "Historical roster" : "Your roster"}
                </h2>
              </div>
              {!data.historical_roster_unavailable && (
                <span className="muted">{data.roster.length} players</span>
              )}
            </div>
            {data.historical_roster_unavailable ? (
              <div className="inline-empty">
                <h3>That roster hasn’t been captured.</h3>
                <p>
                  The matchup above shows its saved official total. The current roster is not
                  substituted for a historical lineup.
                </p>
                <button type="button" className="text-link" onClick={() => set("period", "")}>
                  See the current roster <Arrow />
                </button>
              </div>
            ) : (
              <>
                <div className="roster-controls">
                  <div className="position-filter">
                    <label htmlFor="roster-position">Position</label>
                    <select
                      id="roster-position"
                      value={position}
                      onChange={(event) => set("position", event.target.value)}
                    >
                      <option value="">All positions</option>
                      {["QB", "RB", "WR", "TE", "K", "DST"].map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    className={`filter-button ${watchOnly ? "selected" : ""}`}
                    aria-pressed={watchOnly}
                    onClick={() => set("watched", watchOnly ? "" : "true")}
                  >
                    Watchlist{watchOnly ? " ✓" : ""}
                  </button>
                </div>
                {roster.length ? (
                  <div className="table-wrap">
                    <table className="roster-table">
                      <caption className="sr-only">
                        Your roster. Official points are for scoring period{" "}
                        {data.snapshot.scoring_period}.
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Slot</th>
                          <th scope="col">Player</th>
                          <th scope="col" className="player-status-heading">
                            Status
                          </th>
                          <th scope="col" className="numeric">
                            Official pts
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {roster.map((player) => (
                          <tr key={player.id}>
                            <td>
                              <span className="slot-tag">{player.lineup_slot ?? "—"}</span>
                            </td>
                            <td>
                              <button
                                type="button"
                                className="player-link"
                                onClick={() => openPlayer(player.id)}
                              >
                                {player.display_name}
                                {me?.preferences.watchlist.includes(player.id) && (
                                  <span
                                    role="img"
                                    aria-label="On watchlist"
                                    className="watched-star"
                                  >
                                    ✦
                                  </span>
                                )}
                              </button>
                              <div className="player-subline">
                                <span>{player.position}</span>
                                <span className="mobile-status">
                                  {player.injury_status ||
                                    (player.lineup_locked
                                      ? "Lineup locked"
                                      : !player.active
                                        ? "Not active"
                                        : "")}
                                </span>
                              </div>
                            </td>
                            <td className="player-status">
                              <span className={player.injured ? "injury-label" : "muted"}>
                                {player.injury_status ||
                                  (player.injured
                                    ? "Injury reported"
                                    : !player.active
                                      ? "Not active"
                                      : "—")}
                              </span>
                              {player.lineup_locked && (
                                <span className="lock-label">Lineup locked</span>
                              )}
                            </td>
                            <td className="numeric score-cell">
                              <span>
                                {points(player.official_current_points)}
                                {player.official_current_points === null && (
                                  <span className="sr-only"> Score unavailable</span>
                                )}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="inline-empty">
                    <p>
                      {data.roster.length === 0
                        ? "No roster facts are available in this saved league view."
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
                <p className="table-footnote">
                  Scoring period {data.snapshot.scoring_period} · Locks and health are as reported
                  by ESPN. A dash means unavailable.
                </p>
              </>
            )}
          </section>
        </div>
        <aside className="office-rail">
          <section className="analysis-panel" aria-labelledby="analysis-heading">
            <p className="eyebrow">Your next decision</p>
            <h2 id="analysis-heading">
              Facts first.
              <br />
              <em>Insight follows.</em>
            </h2>
            <p>
              Player evaluations and recommendations will follow once the shared model has been
              built and verified.
            </p>
            <Link to="/model" className="text-link">
              About player analysis <Arrow />
            </Link>
          </section>
          <section className="standings-section" aria-labelledby="standings-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Around the FFA</p>
                <h2 id="standings-heading">League table</h2>
              </div>
            </div>
            <p className="table-context">Current saved season totals</p>
            <div className="table-wrap">
              <table className="standings-table">
                <caption className="sr-only">
                  Current league standings in ESPN source order. Seed is the reported playoff seed,
                  not a forecast.
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
                      Seed
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.standings.map((team) => (
                    <tr key={team.id} className={team.id === data.team.id ? "own-standing" : ""}>
                      <th scope="row">
                        {team.name}
                        {team.id === data.team.id && <span className="you-label">You</span>}
                      </th>
                      <td className="numeric">{record(team)}</td>
                      <td className="numeric">{points(team.points_for)}</td>
                      <td className="numeric">{team.playoff_seed ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="table-footnote">
              Seed is the reported playoff seed. League order is supplied by ESPN.
            </p>
          </section>
          <div className="league-note">
            <span className="league-note-rule" />
            <p>Built for the FFA.</p>
            <span>
              One annual redraft league.
              <br />A clearer view of your team.
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
function ScoreTeam({
  team,
  score,
  own = false,
}: {
  team?: Team;
  score?: string | null;
  own?: boolean;
}) {
  return (
    <div className={`score-team ${own ? "own-team" : ""}`}>
      <div className="team-monogram" aria-hidden="true">
        {team?.abbreviation || "?"}
      </div>
      <p className="team-context">{own ? "Your team" : "Opponent"}</p>
      <h3>{team?.name ?? "Opponent unavailable"}</h3>
      <p className="team-record">{team ? record(team) : "Record unavailable"}</p>
      <p className="matchup-score">
        {points(score)}
        {score == null && <span className="sr-only"> Score unavailable</span>}
        <span>pts</span>
      </p>
    </div>
  );
}
