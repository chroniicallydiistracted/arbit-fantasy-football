import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";
import { useFallbackInterval } from "./events";
import { ageLabel } from "./format";
import {
  BallMark,
  Drives,
  FieldStrip,
  type Game,
  GameBoard,
  type GameDetail,
  IN_PLAY,
  Leaders,
  periodLabel,
  ReadAt,
  statusLine,
  TeamStats,
  teamColor,
  trailing,
  WinChart,
} from "./GameBoard";
import type { components } from "./generated/api";
import { Busy, Notice, PageTitle, StatePanel } from "./primitives";
import { useSession } from "./session";
import { http } from "./transport";
import { useViewingTeam } from "./viewing";

type Games = components["schemas"]["LiveGames"];
type Plays = components["schemas"]["LivePlays"];

const PHASE_ORDER: Record<string, number> = {
  in_progress: 0,
  overtime: 0,
  halftime: 0,
  delayed: 0,
  scheduled: 1,
  final: 2,
};
// The dev account shows the players of the team it chose to view in Front Office (R-039).
function useTeamContext() {
  const { me } = useSession();
  const viewing = useViewingTeam();
  return me?.observer && viewing ? viewing : null;
}

function withTeam(path: string, team: string | null) {
  if (!team) return path;
  return `${path}${path.includes("?") ? "&" : "?"}team_id=${encodeURIComponent(team)}`;
}

export function LiveBoard() {
  const interval = useFallbackInterval();
  const { eventId } = useParams();
  const team = useTeamContext();
  const query = useQuery({
    queryKey: ["live-games", team],
    queryFn: ({ signal }) => http<Games>(withTeam("/api/v1/live/games", team), { signal }),
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
          {eventId && <GameDetailPanel eventId={eventId} />}
        </div>
      )}
    </>
  );
}

function GameTile({ game, selected }: { game: Game; selected: boolean }) {
  const situation = game.situation;
  const sides = [
    { key: "away", team: game.away, other: game.home },
    { key: "home", team: game.home, other: game.away },
  ];
  return (
    <li>
      <Link
        className="game-tile"
        to={`/live/games/${game.event_id}`}
        data-live={IN_PLAY.has(game.phase)}
        aria-current={selected ? "true" : undefined}
      >
        <span className="game-status">
          <span>{statusLine(game)}</span>
          {game.broadcast.length > 0 && <span className="game-channel">{game.broadcast[0]}</span>}
        </span>
        {sides.map(({ key, team, other }) => (
          <span
            className="game-line"
            key={key}
            data-trailing={trailing(game, team, other)}
            style={teamColor(team)}
          >
            <i className="team-tick" />
            <b>{team.abbreviation ?? "—"}</b>
            {team.has_ball ? <BallMark /> : <span />}
            <span className="game-record">{team.record}</span>
            <span className="game-score" data-unknown={team.score == null}>
              {team.score ?? "—"}
            </span>
          </span>
        ))}
        {situation && (situation.short_text || situation.field_text) && (
          <span className="game-down" data-redzone={situation.red_zone === true}>
            {[situation.short_text, situation.field_text].filter(Boolean).join(" · ")}
          </span>
        )}
        <FieldStrip game={game} compact />
        {game.own_players.length > 0 && (
          <span className="game-own">
            <b>{game.own_players.length} yours</b> {game.own_players.join(", ")}
          </span>
        )}
      </Link>
    </li>
  );
}

function GameDetailPanel({ eventId }: { eventId: string }) {
  const interval = useFallbackInterval();
  const team = useTeamContext();
  const query = useQuery({
    queryKey: ["live-game", eventId, team],
    queryFn: ({ signal }) =>
      http<GameDetail>(withTeam(`/api/v1/live/games/${encodeURIComponent(eventId)}`, team), {
        signal,
      }),
    refetchInterval: interval,
  });
  if (query.isPending) return <Busy label="Loading game…" />;
  if (!query.data) return <Notice danger>This game couldn’t be loaded.</Notice>;
  const detail = query.data;
  return (
    <div className="game-page">
      <GameBoard game={detail.game} />
      <p className="table-foot game-read">
        <ReadAt when={detail.game.observed_at} /> from ESPN.{" "}
        <Link className="link-button quiet" to="/live">
          All games
        </Link>
      </p>
      <div className="game-columns">
        <PlayFeed eventId={eventId} />
        <div className="game-rail">
          <WinChart detail={detail} />
          <TeamStats detail={detail} />
          <Leaders detail={detail} />
          <Drives detail={detail} />
        </div>
      </div>
    </div>
  );
}

function PlayFeed({ eventId }: { eventId: string }) {
  const interval = useFallbackInterval();
  const [params, setParams] = useSearchParams();
  const own = params.get("own") === "true";
  const team = useTeamContext();
  const query = useQuery({
    queryKey: ["live-plays", eventId, own, team],
    queryFn: ({ signal }) =>
      http<Plays>(
        withTeam(`/api/v1/live/games/${encodeURIComponent(eventId)}/plays?own=${own}`, team),
        { signal },
      ),
    refetchInterval: interval,
  });
  return (
    <section className="play-feed" aria-labelledby="plays-heading">
      <div className="section-head">
        <h3 id="plays-heading">Plays</h3>
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
          Provider play data, unofficial until ESPN Fantasy settles it.{" "}
          <ReadAt when={query.data.plays_observed_at} />.
        </p>
      )}
    </section>
  );
}
