import { type CSSProperties, useEffect, useRef, useState } from "react";
import { ageLabel, dateLabel } from "./format";
import type { components } from "./generated/api";

export type Game = components["schemas"]["LiveGameRow"];
export type GameDetail = components["schemas"]["LiveGameDetail"];
type Team = components["schemas"]["LiveTeam"];

export const IN_PLAY = new Set(["in_progress", "halftime", "overtime", "delayed"]);

export function periodLabel(period: number | null) {
  if (period == null) return "";
  return period > 4 ? (period === 5 ? "OT" : `${period - 4}OT`) : `Q${period}`;
}

function kickoffLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function statusLine(game: Game): string {
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

/** Team colors come from ESPN as data, so they travel as a variable rather than a token. */
export function teamColor(team: Team): CSSProperties | undefined {
  return team.color && /^[0-9a-f]{6}$/i.test(team.color)
    ? ({ "--team": `#${team.color}` } as CSSProperties)
    : undefined;
}

export function trailing(game: Game, team: Team, other: Team): boolean {
  if (game.phase === "scheduled" || team.score == null || other.score == null) return false;
  return Number(team.score) < Number(other.score);
}

export function BallMark() {
  return (
    <svg className="ball-mark" viewBox="0 0 16 10" role="img" aria-label="Has the ball">
      <path d="M1 5C4 .5 12 .5 15 5 12 9.5 4 9.5 1 5Z" fill="currentColor" />
    </svg>
  );
}

// The strip reads like the matchup, away on the left and home on the right. ESPN's yard line runs
// from the home goal line, so it maps directly onto the field without knowing who has the ball.
const fromLeft = (yardLine: number) => `${100 - yardLine}%`;
const YARD_MARKS = [10, 20, 30, 40, 50, 60, 70, 80, 90];

export function FieldStrip({ game, compact = false }: { game: Game; compact?: boolean }) {
  const situation = game.situation;
  if (!situation || situation.yard_line == null) return null;
  const holder = situation.possession === "home" ? game.home : game.away;
  const label = [
    `Ball at ${situation.field_text ?? "an unknown spot"}.`,
    situation.possession
      ? `${holder.abbreviation ?? "Team"} driving toward the ${
          situation.possession === "home" ? "left" : "right"
        } end zone.`
      : "Possession unknown.",
    situation.short_text,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="field-strip" data-compact={compact} role="img" aria-label={label}>
      <span className="fs-zone" style={teamColor(game.away)} />
      <div className="fs-field">
        {situation.first_down_line != null && (
          <i className="fs-first" style={{ left: fromLeft(situation.first_down_line) }} />
        )}
        {(!compact || !situation.possession) && (
          <i className="fs-los" style={{ left: fromLeft(situation.yard_line) }} />
        )}
        {situation.possession && (
          <span
            className="fs-ball"
            data-toward={situation.possession === "home" ? "left" : "right"}
            style={{ left: fromLeft(situation.yard_line) }}
          >
            <svg viewBox="0 0 28 10" aria-hidden="true">
              <path d="M1 5C4 .5 12 .5 15 5 12 9.5 4 9.5 1 5Z" fill="currentColor" />
              <path d="M19 1.5 26 5 19 8.5Z" fill="currentColor" />
            </svg>
          </span>
        )}
      </div>
      <span className="fs-zone" style={teamColor(game.home)} />
      {!compact && (
        <>
          <span className="fs-name">{game.away.abbreviation}</span>
          <span className="fs-yards" aria-hidden="true">
            {YARD_MARKS.map((mark) => (
              <span key={mark} style={{ left: `${mark}%` }}>
                {mark <= 50 ? mark : 100 - mark}
              </span>
            ))}
          </span>
          <span className="fs-name">{game.home.abbreviation}</span>
        </>
      )}
    </div>
  );
}

/** True for a moment after a value changes, not when it first appears. */
function useJustChanged(value: string | null): boolean {
  const previous = useRef(value);
  const [changed, setChanged] = useState(false);
  useEffect(() => {
    if (previous.current === value) return;
    const hadValue = previous.current != null;
    previous.current = value;
    if (!hadValue) return;
    setChanged(true);
    const timer = window.setTimeout(() => setChanged(false), 1600);
    return () => window.clearTimeout(timer);
  }, [value]);
  return changed;
}

function Timeouts({ left }: { left: number }) {
  return (
    <span className="gb-timeouts" role="img" aria-label={`${left} timeouts left`}>
      {[0, 1, 2].map((slot) => (
        <i key={slot} data-used={slot >= left} />
      ))}
    </span>
  );
}

function TeamSide({
  game,
  team,
  other,
  side,
}: {
  game: Game;
  team: Team;
  other: Team;
  side: string;
}) {
  const changed = useJustChanged(team.score);
  return (
    <div
      className="gb-team"
      data-side={side}
      data-trailing={trailing(game, team, other)}
      style={teamColor(team)}
    >
      <span className="gb-band" />
      <div className="gb-id">
        <div className="gb-name">
          <b>{team.abbreviation ?? "—"}</b>
          {team.has_ball && <BallMark />}
        </div>
        <span className="gb-full">{team.name}</span>
        <span className="gb-record">
          {team.record}
          {team.timeouts != null && <Timeouts left={team.timeouts} />}
        </span>
      </div>
      <span className="gb-points" data-unknown={team.score == null} data-changed={changed}>
        {team.score ?? "—"}
      </span>
    </div>
  );
}

function Linescore({ game }: { game: Game }) {
  const played = Math.max(game.away.periods.length, game.home.periods.length);
  if (played === 0) return null;
  const columns = Array.from({ length: Math.max(4, played) }, (_, index) => index);
  const row = (team: Team) => (
    <tr key={team.abbreviation}>
      <th scope="row">{team.abbreviation ?? "—"}</th>
      {columns.map((column) => (
        <td key={column} data-now={IN_PLAY.has(game.phase) && column === played - 1}>
          {team.periods[column] ?? ""}
        </td>
      ))}
      <td className="gb-total">{team.score ?? "—"}</td>
    </tr>
  );
  return (
    <div className="table-scroll">
      <table className="gb-lines">
        <caption className="sr-only">Score by quarter</caption>
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">Team</span>
            </th>
            {columns.map((column) => (
              <th key={column} scope="col">
                {periodLabel(column + 1)}
              </th>
            ))}
            <th scope="col">T</th>
          </tr>
        </thead>
        <tbody>
          {row(game.away)}
          {row(game.home)}
        </tbody>
      </table>
    </div>
  );
}

function clockLines(game: Game): string[] {
  if (game.phase === "in_progress" || game.phase === "overtime") {
    return [periodLabel(game.period), game.clock ?? ""].filter(Boolean);
  }
  return [statusLine(game)];
}

function matchupSummary(game: Game): string {
  const score = `${game.away.abbreviation ?? "Away"} ${game.away.score ?? "unknown"}, ${
    game.home.abbreviation ?? "Home"
  } ${game.home.score ?? "unknown"}.`;
  const down = game.situation?.short_text;
  return [statusLine(game), score, down, game.situation?.field_text].filter(Boolean).join(" ");
}

/** ESPN's text often opens with its own type, so the label would just repeat it. */
function lastPlayKind(play: { kind: string | null; text: string | null }): string | null {
  return play.kind && !play.text?.trim().startsWith(play.kind) ? play.kind : null;
}

export function GameBoard({ game }: { game: Game }) {
  const situation = game.situation;
  const place = [game.venue?.name, game.venue?.city].filter(Boolean).join(", ");
  const weather = game.venue?.indoor
    ? "Indoors"
    : [
        game.weather?.temperature != null ? `${game.weather.temperature}°` : null,
        game.weather?.condition,
      ]
        .filter(Boolean)
        .join(" ");
  return (
    <section
      className="game-board"
      data-live={IN_PLAY.has(game.phase)}
      aria-labelledby="game-heading"
    >
      <p className="sr-only" role="status">
        {matchupSummary(game)}
      </p>
      <header className="gb-meta">
        <h2 id="game-heading">
          {game.away.abbreviation ?? "—"} at {game.home.abbreviation ?? "—"}
        </h2>
        <span className="gb-state">{statusLine(game)}</span>
        {game.broadcast.length > 0 && <span>{game.broadcast.join(", ")}</span>}
        {place && <span>{place}</span>}
        {weather && <span>{weather}</span>}
      </header>
      <div className="gb-teams">
        <TeamSide game={game} team={game.away} other={game.home} side="away" />
        <div className="gb-clock" aria-hidden="true">
          {clockLines(game).map((line) => (
            <span key={line}>{line}</span>
          ))}
        </div>
        <TeamSide game={game} team={game.home} other={game.away} side="home" />
      </div>
      {situation && (situation.short_text || situation.field_text || situation.red_zone) && (
        <div className="gb-down">
          {situation.short_text && <b>{situation.short_text}</b>}
          {situation.field_text && <span>{situation.field_text}</span>}
          {situation.red_zone && <span className="gb-redzone">Red zone</span>}
        </div>
      )}
      <FieldStrip game={game} />
      {situation?.last_play?.text && (
        <p className="gb-last">
          {lastPlayKind(situation.last_play) && <b>{lastPlayKind(situation.last_play)}</b>}{" "}
          {situation.last_play.text.trim()}
        </p>
      )}
      <Linescore game={game} />
    </section>
  );
}

export function WinChart({ detail }: { detail: GameDetail }) {
  const points = detail.win_probability;
  if (points.length < 2) return null;
  const { home, away } = detail.game;
  const last = points[points.length - 1]?.home ?? 0.5;
  const leader = last >= 0.5 ? home : away;
  const share = Math.round((last >= 0.5 ? last : 1 - last) * 100);
  // Up means the home team's chances rise. Modeled values are dashed and in the modeled color.
  const line = points
    .map((point, index) => `${(index / (points.length - 1)) * 100},${(1 - point.home) * 40}`)
    .join(" ");
  const summary = `ESPN's win probability: ${leader.abbreviation ?? "leader"} ${share}%, across ${points.length} plays.`;
  return (
    <figure className="win-chart">
      <figcaption>
        <span>Win probability</span>
        <b>
          {leader.abbreviation} {share}%
        </b>
      </figcaption>
      <div className="win-plot">
        <span className="win-side">{home.abbreviation}</span>
        <svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label={summary}>
          <line x1="0" y1="20" x2="100" y2="20" />
          <polyline points={line} vectorEffect="non-scaling-stroke" />
        </svg>
        <span className="win-side">{away.abbreviation}</span>
      </div>
      <p className="table-foot">ESPN's model.</p>
    </figure>
  );
}

const STAT_ORDER = [
  "totalYards",
  "netPassingYards",
  "rushingYards",
  "firstDowns",
  "thirdDownEff",
  "fourthDownEff",
  "redZoneAttempts",
  "turnovers",
  "sacksYardsLost",
  "totalPenaltiesYards",
  "possessionTime",
];

export function TeamStats({ detail }: { detail: GameDetail }) {
  const rows = STAT_ORDER.flatMap((key) => detail.team_stats.filter((stat) => stat.key === key));
  if (rows.length === 0) return null;
  const { home, away } = detail.game;
  return (
    <section aria-labelledby="stats-heading">
      <div className="section-head">
        <h3 id="stats-heading">Team stats</h3>
      </div>
      <table className="agate">
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">Statistic</span>
            </th>
            <th scope="col" className="numeric">
              {away.abbreviation}
            </th>
            <th scope="col" className="numeric">
              {home.abbreviation}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((stat) => (
            <tr key={stat.key}>
              <th scope="row">{stat.label ?? stat.key}</th>
              <td className="numeric">{stat.away ?? "—"}</td>
              <td className="numeric">{stat.home ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function Leaders({ detail }: { detail: GameDetail }) {
  if (detail.leaders.length === 0) return null;
  return (
    <section aria-labelledby="leaders-heading">
      <div className="section-head">
        <h3 id="leaders-heading">Leaders</h3>
      </div>
      <table className="agate">
        <tbody>
          {detail.leaders.map((leader) => (
            <tr key={leader.category}>
              <th scope="row">{leader.category}</th>
              <td>
                {leader.name ?? "—"} <span className="muted">{leader.team}</span>
              </td>
              <td className="numeric">{leader.line}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function Drives({ detail }: { detail: GameDetail }) {
  if (detail.drives.length === 0) return null;
  const newestFirst = [...detail.drives].reverse();
  return (
    <section aria-labelledby="drives-heading">
      <div className="section-head">
        <h3 id="drives-heading">Drives</h3>
      </div>
      <div className="table-scroll">
        <table className="agate">
          <thead>
            <tr>
              <th scope="col">Team</th>
              <th scope="col">Result</th>
              <th scope="col" className="numeric">
                Plays
              </th>
              <th scope="col" className="numeric">
                Yds
              </th>
              <th scope="col" className="numeric">
                Time
              </th>
              <th scope="col">Start</th>
            </tr>
          </thead>
          <tbody>
            {newestFirst.map((drive) => (
              <tr
                key={`${drive.team}-${drive.start}-${drive.end}-${drive.plays}`}
                data-scored={drive.scored === true}
              >
                <th scope="row">{drive.team ?? "—"}</th>
                <td>
                  {drive.current ? (
                    <span className="tag tag-caution">Current</span>
                  ) : (
                    (drive.result ?? "—")
                  )}
                </td>
                <td className="numeric">{drive.plays ?? "—"}</td>
                <td className="numeric">{drive.yards ?? "—"}</td>
                <td className="numeric">{drive.elapsed ?? "—"}</td>
                <td>{drive.start ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ReadAt({ when, prefix = "Read" }: { when: string; prefix?: string }) {
  return (
    <>
      {prefix}{" "}
      <time dateTime={when} title={dateLabel(when)}>
        {ageLabel(when)}
      </time>
    </>
  );
}
