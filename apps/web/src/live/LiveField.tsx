// The live field (OWN-042): the game's plays drawn in real time from their scripts, in the
// full-field view, with the stadium board. A new play arrives over the event stream and plays
// next; any earlier play can be replayed. The canvas is decoration: the play feed below stays the
// readable, accessible record of the same plays.
import { useQuery } from "@tanstack/react-query";
import {
  Component,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router";
import { useFallbackInterval } from "../events";
import { type Game, GameBoard, GameScoreStatus } from "../GameBoard";
import type { components } from "../generated/api";
import { http } from "../transport";
import { drawBoard, LedBoard, type Team } from "./led";
import { type Art, type Meta, Scene } from "./scene";

type Animation = components["schemas"]["LiveAnimation"];
type Entry = components["schemas"]["LiveAnimationEntry"];

const NOTE = "Re-creation from play-by-play";

async function image(url: string): Promise<HTMLImageElement> {
  const element = new Image();
  element.src = url;
  await element.decode();
  return element;
}

async function loadArt(eventId: string, revision?: string | null): Promise<Art> {
  const base = `/api/v1/live/art/${encodeURIComponent(eventId)}`;
  const asset = (name: string) => `${base}/${name}${revision ? `?revision=${revision}` : ""}`;
  const meta = await http<Meta>(asset("meta.json"));
  const [field, home, away, officials, ball] = await Promise.all([
    image(asset("field.png")),
    image(asset(meta.teams.home.sprites.image)),
    image(asset(meta.teams.away.sprites.image)),
    image(asset("officials.png")),
    image(asset("ball.png")),
  ]);
  return { meta, field, sprites: { home, away }, officials, ball };
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );
  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!query) return;
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

type Clip = { entry: Entry; scene: Scene; board: LedBoard | null; length: number };

const keyOf = (entry: Entry) => `${entry.play_id}:${entry.part}`;

// A failure in the field hides the field only: the scoreboard and the play feed stay up.
class FieldBoundary extends Component<{ children: ReactNode; game: Game }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <FieldUnavailable game={this.props.game}>
        The field couldn’t be drawn for this game.
      </FieldUnavailable>
    ) : (
      this.props.children
    );
  }
}

function FieldUnavailable({ game, children }: { game: Game; children: ReactNode }) {
  return (
    <>
      <GameBoard game={game} />
      <p className="live-field-note">{children}</p>
    </>
  );
}

export function LiveField({ eventId, game }: { eventId: string; game: Game }) {
  return (
    <FieldBoundary key={eventId} game={game}>
      <Field eventId={eventId} game={game} />
    </FieldBoundary>
  );
}

function Field({ eventId, game }: { eventId: string; game: Game }) {
  const interval = useFallbackInterval();
  const animation = useQuery({
    queryKey: ["live-animation", eventId],
    queryFn: ({ signal }) =>
      http<Animation>(`/api/v1/live/games/${encodeURIComponent(eventId)}/animation`, { signal }),
    refetchInterval: interval,
  });
  const art = useQuery({
    queryKey: ["live-art", eventId, animation.data?.art.revision],
    queryFn: () => loadArt(eventId, animation.data?.art.revision),
    enabled: animation.data?.art.available === true,
    staleTime: 10 * 60_000,
  });
  const reduced = usePrefersReducedMotion();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("play");
  const selectedKey = selectedId
    ? `${selectedId}:${params.get("part") === "try" ? "try" : "play"}`
    : null;
  const [live, setLive] = useState<string | null>(null);
  const remembered = useRef<Entry | null>(null);
  const [paused, setPaused] = useState(false);
  const [drawFailed, setDrawFailed] = useState(false);
  const [epoch, setEpoch] = useState(0); // a replay restarts the same play
  const clock = useRef({ started: performance.now(), frozen: 0 });

  const entries = animation.data?.entries;
  const home = animation.data?.home;
  const away = animation.data?.away;
  const teams = useMemo(() => {
    if (!home || !away || !art.data) return {};
    const { meta } = art.data;
    return {
      [home]: {
        color: meta.teams.home.tag[0] as [number, number, number],
        logo: meta.teams.home.logo,
      },
      [away]: {
        color: meta.teams.away.tag[0] as [number, number, number],
        logo: meta.teams.away.logo,
      },
    } satisfies Record<string, Team>;
  }, [home, away, art.data]);
  // React Query preserves unchanged entry objects. Keep their scenes and board frames on refetch.
  const rendered = useRef(new WeakMap<Entry, Clip>());
  const clips = useMemo(() => {
    const artData = art.data;
    if (!entries || !home || !artData) return [];
    return entries.flatMap((entry) => {
      const script = entry.script;
      if (!script || entry.cancelled) return [];
      const existing = rendered.current.get(entry);
      if (existing?.scene.art === artData) return [existing];
      const board = entry.board
        ? new LedBoard(entry.board, script.whistle, teams, !script.note)
        : null;
      const clip = {
        entry,
        scene: new Scene(script, artData, home),
        board,
        length: Math.max(script.duration, board?.length ?? 0),
      };
      rendered.current.set(entry, clip);
      return [clip];
    });
  }, [home, art.data, entries, teams]);
  const newest = clips.at(-1);
  const liveIndex = clips.findIndex((clip) => keyOf(clip.entry) === live);
  const liveClip =
    reduced || liveIndex < 0
      ? newest
      : clips[clips.length - 1 - liveIndex > 3 ? clips.length - 3 : liveIndex];
  const followKey = liveClip && keyOf(liveClip.entry);
  useEffect(() => {
    if (!selectedKey && followKey) setLive(followKey);
  }, [selectedKey, followKey]);
  const selected = selectedKey ? entries?.find((entry) => keyOf(entry) === selectedKey) : undefined;
  useEffect(() => {
    if (selected) remembered.current = selected;
  }, [selected]);
  const missing = Boolean(selectedKey && !selected && entries);
  const parentPlay =
    missing && selectedId && params.get("part") === "try"
      ? entries?.find((item) => item.play_id === selectedId && item.part === "play")
      : undefined;
  const current = selectedKey ? clips.find((clip) => keyOf(clip.entry) === selectedKey) : liveClip;
  const entry = selectedKey
    ? (selected ??
      parentPlay ??
      (remembered.current && keyOf(remembered.current) === selectedKey
        ? remembered.current
        : undefined))
    : (current?.entry ?? entries?.at(-1));
  const last = entries?.at(-1);
  const laterBoardEntry =
    !selectedKey && current === newest && last !== current?.entry ? last : undefined;
  const stillEntry = current ? laterBoardEntry : (selected ?? (!selectedKey ? last : undefined));
  const stillBoard = useMemo(
    () => (stillEntry?.board ? new LedBoard(stillEntry.board, 0, teams) : null),
    [stillEntry, teams],
  );
  const targetKey = entry && keyOf(entry);
  // biome-ignore lint/correctness/useExhaustiveDependencies: a new play or replay restarts the clock
  useEffect(() => {
    clock.current = { started: performance.now(), frozen: 0 };
  }, [targetKey, epoch]);

  const final = !selectedKey && current === newest && game.phase === "final";
  const font = useMemo(() => getComputedStyle(document.body).fontFamily || "sans-serif", []);

  const drawAt = useCallback(
    (clip: Clip | undefined, t: number, terminal: boolean) => {
      const element = canvas.current;
      if (!element || !art.data) return;
      const ctx = element.getContext("2d");
      if (!ctx) throw new Error("Canvas unavailable");
      const meta = art.data.meta;
      ctx.drawImage(art.data.field, 0, 0);
      const boardImage =
        terminal && (stillBoard || final)
          ? (stillBoard ?? clip?.board)?.after(final ? "FINAL" : undefined)
          : clip?.board?.at(t);
      if (boardImage) {
        const top = meta.board.top - meta.band.top;
        const image = boardImage;
        drawBoard(ctx, image, meta.camera.width, top, top + image.height + 16);
      }
      clip?.scene.draw(ctx, t, font);
      const bar = meta.camera.caption_size + 21;
      const bottom = element.height;
      ctx.fillStyle = "rgba(10,12,14,0.894)";
      ctx.fillRect(0, bottom - bar, element.width, bar);
      ctx.textBaseline = "top";
      ctx.fillStyle = "rgb(240,240,235)";
      ctx.font = `${meta.camera.caption_size}px ${font}`;
      const caption = clip?.scene.script.caption ?? entry?.text;
      if (caption) ctx.fillText(caption, 16, bottom - bar + 8, element.width - 560);
      const notes = [
        NOTE,
        ...Object.values(meta.labels).filter(Boolean),
        (terminal ? (stillEntry ?? entry) : entry)?.source === "espn"
          ? "Fallback source: ESPN"
          : null,
      ]
        .filter(Boolean)
        .join(" · ");
      ctx.font = `${meta.camera.tag_size}px ${font}`;
      ctx.fillStyle = "rgb(200,205,200)";
      ctx.fillText(
        notes,
        element.width - 16 - ctx.measureText(notes).width,
        bottom - bar / 2 - meta.camera.tag_size / 2 - 1,
      );
    },
    [art.data, font, entry, final, stillBoard, stillEntry],
  );

  const currentIndex = current ? clips.indexOf(current) : -1;
  const nextLive = currentIndex >= 0 ? clips[currentIndex + 1] : undefined;
  // biome-ignore lint/correctness/useExhaustiveDependencies: a replay (epoch) redraws from the start
  useEffect(() => {
    if (drawFailed || !art.data || (!current && !stillBoard && !entry && !missing)) return;
    let frame = 0;
    const tick = (now: number) => {
      const elapsed = paused ? clock.current.frozen : (now - clock.current.started) / 1000;
      const length = current?.length ?? 0;
      const terminal = !current || reduced || elapsed >= length;
      const t = terminal ? length : elapsed;
      try {
        drawAt(current, t, terminal);
      } catch {
        setDrawFailed(true);
        return;
      }
      if (!current || reduced || paused) return;
      if (!terminal) frame = requestAnimationFrame(tick);
      else if (!selectedKey && nextLive) setLive(keyOf(nextLive.entry));
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [
    art.data,
    current,
    drawAt,
    drawFailed,
    entry,
    epoch,
    missing,
    nextLive,
    paused,
    reduced,
    selectedKey,
    stillBoard,
  ]);

  const togglePause = () => {
    if (!current) return;
    if (!paused) clock.current.frozen = (performance.now() - clock.current.started) / 1000;
    else clock.current.started = performance.now() - clock.current.frozen * 1000;
    setPaused(!paused);
  };
  const go = (clip: Clip | null) => {
    setPaused(false);
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (clip) next.set("play", clip.entry.play_id);
        else next.delete("play");
        if (clip?.entry.part === "try") next.set("part", "try");
        else next.delete("part");
        return next;
      },
      { replace: true },
    );
    if (!clip) setLive(newest ? keyOf(newest.entry) : null);
    setEpoch((value) => value + 1);
  };
  const order = selected && entries ? entries.indexOf(selected) : -1;
  const previous = current
    ? clips[currentIndex - 1]
    : order >= 0
      ? clips.filter((clip) => (entries?.indexOf(clip.entry) ?? -1) < order).at(-1)
      : undefined;
  const next = current
    ? nextLive
    : order >= 0
      ? clips.find((clip) => (entries?.indexOf(clip.entry) ?? -1) > order)
      : undefined;
  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "k") togglePause();
    else if (event.key === "ArrowLeft" && previous) go(previous);
    else if (event.key === "ArrowRight" && next) go(next);
    else if (event.key === "r" && current) go(current);
    else if (event.key === "l") go(null);
    else return;
    event.preventDefault();
  };
  const noPlay = missing || selected?.cancelled;
  const noArt = !art.data || art.isError || drawFailed;
  const note = current?.scene.script.note;
  const notice = (note ||
    (selectedKey && (noPlay || (selected && (!selected.script || noArt))))) && (
    <p className="live-field-note" role="status">
      <b>{noPlay ? "No Play" : note ? "Partial re-creation" : "Text replay"}</b>{" "}
      {note && `${note} `}
      {entry?.text ?? "This play is no longer in the feed."}
    </p>
  );

  if (!animation.data) return <GameBoard game={game} />;
  if (!animation.data.art.available) {
    return (
      <>
        <FieldUnavailable game={game}>
          The field art for this game is still pending.
        </FieldUnavailable>
        {notice}
      </>
    );
  }
  if (art.isError)
    return (
      <>
        <FieldUnavailable game={game}>The field's art couldn't be loaded.</FieldUnavailable>
        {notice}
      </>
    );
  if (drawFailed)
    return (
      <>
        <FieldUnavailable game={game}>The field couldn’t be drawn for this game.</FieldUnavailable>
        {notice}
      </>
    );
  if (!art.data) return <GameBoard game={game} />;
  if (!entry && !missing)
    return (
      <>
        <GameBoard game={game} />
        <EmptyField art={art.data} />
      </>
    );
  const meta = art.data.meta;
  const hasBoard = Boolean(current?.board || stillBoard);
  return (
    <>
      {hasBoard ? <GameScoreStatus game={game} /> : <GameBoard game={game} />}
      <section id="live-field" className="live-field" aria-label="Live field">
        <button
          type="button"
          className="live-field-stage"
          onClick={togglePause}
          onKeyDown={onKey}
          aria-label={`Live field, ${paused ? "paused" : "playing"}. Press to ${paused ? "play" : "pause"}; arrow keys step between plays.`}
          aria-describedby="live-field-keys"
        >
          <canvas
            ref={canvas}
            width={meta.camera.width}
            height={meta.band.bottom - meta.band.top}
          />
        </button>
        <div className="live-field-controls">
          <button
            type="button"
            className="quiet"
            onClick={() => previous && go(previous)}
            disabled={!previous}
          >
            Previous play
          </button>
          <button
            type="button"
            className="quiet"
            onClick={() => current && go(current)}
            disabled={!current}
          >
            Replay
          </button>
          <button
            type="button"
            className="quiet"
            onClick={togglePause}
            aria-pressed={paused}
            disabled={!current}
          >
            {paused ? "Play" : "Pause"}
          </button>
          <button type="button" className="quiet" onClick={() => next && go(next)} disabled={!next}>
            Next play
          </button>
          <button
            type="button"
            className="quiet"
            onClick={() => go(null)}
            aria-pressed={!selectedKey}
          >
            Live
          </button>
          <span className="live-field-now">
            {entry?.period ? `Q${entry.period} ${entry.clock ?? ""}` : ""}{" "}
            {entry?.part === "try" ? "· Try" : ""}
          </span>
        </div>
        {notice}
        <p id="live-field-keys" className="live-field-note">
          Keys on the field: Enter or space pauses, arrows step between plays, R replays, L follows
          the game live.
          {reduced ? " Motion is reduced: each play shows where it ended." : ""}
        </p>
      </section>
      {hasBoard && (
        <details className="game-score-details">
          <summary>Game details and score by quarter</summary>
          <GameBoard game={game} announce={false} />
        </details>
      )}
    </>
  );
}

// Before the first play: the game's field, waiting for the kickoff.
function EmptyField({ art }: { art: Art }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    canvas.current?.getContext("2d")?.drawImage(art.field, 0, 0);
  }, [art]);
  return (
    <section className="live-field" aria-label="Live field">
      <div className="live-field-stage">
        <canvas
          ref={canvas}
          width={art.meta.camera.width}
          height={art.meta.band.bottom - art.meta.band.top}
        />
      </div>
      <p className="live-field-note">
        The field fills in with the first play.
        {Object.values(art.meta.labels).filter(Boolean).length
          ? ` ${Object.values(art.meta.labels).filter(Boolean).join(". ")}.`
          : ""}
      </p>
    </section>
  );
}
