import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";
import { useFallbackInterval } from "./events";
import { ageLabel, dateLabel } from "./format";
import type { components } from "./generated/api";
import { Busy, Notice, PageTitle, StatePanel } from "./primitives";
import { http } from "./transport";

type Games = components["schemas"]["LiveGames"];
type Game = components["schemas"]["LiveGameRow"];
type Plays = components["schemas"]["LivePlays"];

const IN_PLAY = new Set(["in_progress", "halftime", "overtime", "delayed"]);
const PHASE_ORDER: Record<string, number> = {
  in_progress: 0,
  overtime: 0,
  halftime: 0,
  delayed: 0,
  scheduled: 1,
  final: 2,
};
function periodLabel(period: number | null) {
  if (period == null) return "";
  return period > 4 ? (period === 5 ? "OT" : `${period - 4}OT`) : `Q${period}`;
}
function statusLine(game: Game): string {
  switch (game.phase) {
    case "in_progress":
    case "overtime":
      return [periodLabel(game.period), game.clock].filter(Boolean).join(" ");
    case "halftime":
      return "Halftime";
    case "delayed":
      return "Delayed";
    case "final":
      return game.period != null && game.period > 4 ? "Final/OT" : "Final";
    case "postponed":
      return "Postponed";
    case "cancelled":
      return "Cancelled";
    case "scheduled":
      return game.kickoff ? kickoffLabel(game.kickoff) : "Kickoff to be announced";
    default:
      return "Status unknown";
  }
}
function kickoffLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function LiveBoard() {
  const interval = useFallbackInterval();
  const { eventId } = useParams();
  const query = useQuery({
    queryKey: ["live-games"],
    queryFn: ({ signal }) => http<Games>("/api/v1/live/games", { signal }),
    refetchInterval: interval,
  });
  if (query.isPending) return <Busy label="Loading games…" />;
  if (!query.data)
    return (
      <StatePanel title="Live">
        <p>Games couldn’t be loaded.</p>
        <div className="actions">
          <button type="button" className="primary" onClick={() => void query.refetch()}>
            Retry
          </button>
        </div>
      </StatePanel>
    );
  const data = query.data;
  const games = [...data.games].sort(
    (a, b) => (PHASE_ORDER[a.phase] ?? 3) - (PHASE_ORDER[b.phase] ?? 3),
  );
  return (
    <>
      <PageTitle title="Live">
        {data.week != null && <span className="muted">Week {data.week}</span>}
      </PageTitle>
      {(data.source_state === "behind" || data.source_state === "down") && (
        <Notice>
          Scores are behind ESPN.
          {data.last_success_at ? ` Last read ${ageLabel(data.last_success_at)}.` : ""}
        </Notice>
      )}
      {games.length === 0 ? (
        <section className="state-panel">
          <p>No games have been read yet. The sync worker fills this once it reaches ESPN.</p>
        </section>
      ) : (
        <div className={eventId ? "live-split" : ""}>
          <ul className="game-grid" aria-label="Games">
            {games.map((game) => (
              <GameTile key={game.event_id} game={game} selected={game.event_id === eventId} />
            ))}
          </ul>
          {eventId && <PlayFeed eventId={eventId} />}
        </div>
      )}
    </>
  );
}

function GameTile({ game, selected }: { game: Game; selected: boolean }) {
  const live = IN_PLAY.has(game.phase);
  const home = Number(game.home.score);
  const away = Number(game.away.score);
  const started = game.home.score != null && game.away.score != null && game.phase !== "scheduled";
  return (
    <li>
      <Link
        className="game-tile"
        to={`/live/games/${game.event_id}`}
        data-live={live}
        aria-current={selected ? "true" : undefined}
      >
        <span className="game-status">{statusLine(game)}</span>
        {[
          { key: "away", team: game.away, trailing: started && away < home },
          { key: "home", team: game.home, trailing: started && home < away },
        ].map(({ key, team, trailing }) => (
          <span className="game-line" key={key} data-trailing={trailing}>
            <b>{team.abbreviation ?? "—"}</b>
            <span className="game-score" data-unknown={team.score == null}>
              {team.score ?? "—"}
            </span>
          </span>
        ))}
        {game.own_players.length > 0 && (
          <span className="game-own">
            <b>{game.own_players.length} yours</b> {game.own_players.join(", ")}
          </span>
        )}
      </Link>
    </li>
  );
}

function PlayFeed({ eventId }: { eventId: string }) {
  const interval = useFallbackInterval();
  const [params, setParams] = useSearchParams();
  const own = params.get("own") === "true";
  const query = useQuery({
    queryKey: ["live-plays", eventId, own],
    queryFn: ({ signal }) =>
      http<Plays>(`/api/v1/live/games/${encodeURIComponent(eventId)}/plays?own=${own}`, { signal }),
    refetchInterval: interval,
  });
  return (
    <section className="play-feed" aria-labelledby="plays-heading">
      <div className="section-head">
        <h2 id="plays-heading">
          {query.data
            ? `${query.data.game.away.abbreviation ?? "—"} at ${query.data.game.home.abbreviation ?? "—"}`
            : "Plays"}
        </h2>
        <div className="section-tools">
          <button
            type="button"
            className="toggle"
            aria-pressed={own}
            onClick={() => {
              const next = new URLSearchParams(params);
              if (own) next.delete("own");
              else next.set("own", "true");
              setParams(next);
            }}
          >
            My players
          </button>
          <Link className="link-button quiet" to="/live">
            Close
          </Link>
        </div>
      </div>
      {query.isPending && <Busy label="Loading plays…" />}
      {query.isError && <Notice danger>Plays couldn’t be loaded.</Notice>}
      {query.data && query.data.plays.length === 0 && (
        <p className="inline-state">
          {own
            ? "None of your players are named in a play yet."
            : query.data.game.phase === "scheduled"
              ? "Plays appear after kickoff."
              : "No plays have been read for this game yet."}
        </p>
      )}
      {query.data && query.data.plays.length > 0 && (
        <ol className="play-list">
          {query.data.plays.map((play) => (
            <li
              key={play.id}
              data-own={play.own}
              data-scoring={play.scoring}
              data-cancelled={play.cancelled}
            >
              <span className="play-when">
                {periodLabel(play.period)} {play.clock}
              </span>
              <span className="play-text">
                {play.text}
                {play.cancelled && <span className="tag tag-fault"> No play</span>}
                {play.corrected && !play.cancelled && (
                  <span className="tag tag-caution"> Corrected</span>
                )}
              </span>
              <span className="play-score numeric">
                {play.scoring ? `${play.away_score ?? "—"}–${play.home_score ?? "—"}` : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
      {query.data?.plays_observed_at && (
        <p className="table-foot">
          Provider play data, unofficial until ESPN Fantasy settles it. Read{" "}
          <time
            dateTime={query.data.plays_observed_at}
            title={dateLabel(query.data.plays_observed_at)}
          >
            {ageLabel(query.data.plays_observed_at)}
          </time>
          .
        </p>
      )}
    </section>
  );
}
