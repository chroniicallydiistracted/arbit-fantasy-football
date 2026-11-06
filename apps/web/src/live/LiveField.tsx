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
import { useFallbackInterval } from "../events";
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

async function loadArt(eventId: string): Promise<Art> {
  const base = `/api/v1/live/art/${encodeURIComponent(eventId)}`;
  const meta = await http<Meta>(`${base}/meta.json`);
  const [field, home, away, officials, ball] = await Promise.all([
    image(`${base}/field.png`),
    image(`${base}/${meta.teams.home.sprites.image}`),
    image(`${base}/${meta.teams.away.sprites.image}`),
    image(`${base}/officials.png`),
    image(`${base}/ball.png`),
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

// A failure in the field hides the field only: the scoreboard and the play feed stay up.
class FieldBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <p className="live-field-note">The field couldn’t be drawn for this game.</p>
    ) : (
      this.props.children
    );
  }
}

export function LiveField({ eventId }: { eventId: string }) {
  return (
    <FieldBoundary>
      <Field eventId={eventId} />
    </FieldBoundary>
  );
}

function Field({ eventId }: { eventId: string }) {
  const interval = useFallbackInterval();
  const animation = useQuery({
    queryKey: ["live-animation", eventId],
    queryFn: ({ signal }) =>
      http<Animation>(`/api/v1/live/games/${encodeURIComponent(eventId)}/animation`, { signal }),
    refetchInterval: interval,
  });
  const art = useQuery({
    queryKey: ["live-art", eventId],
    queryFn: () => loadArt(eventId),
    enabled: animation.data?.art.available === true,
    staleTime: 10 * 60_000,
  });
  const reduced = usePrefersReducedMotion();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [index, setIndex] = useState<number | null>(null); // null follows the game live
  const [live, setLive] = useState(-1); // the play shown while following live
  const [paused, setPaused] = useState(false);
  const [epoch, setEpoch] = useState(0); // a replay restarts the same play
  const clock = useRef({ started: performance.now(), frozen: 0 });

  const clips: Clip[] = useMemo(() => {
    if (!animation.data || !art.data) return [];
    const data = animation.data;
    const meta = art.data.meta;
    const teams: Record<string, Team> = {
      [data.home]: {
        color: meta.teams.home.tag[0] as [number, number, number],
        logo: meta.teams.home.logo,
      },
      [data.away]: {
        color: meta.teams.away.tag[0] as [number, number, number],
        logo: meta.teams.away.logo,
      },
    };
    return data.entries.flatMap((entry) => {
      const script = entry.script;
      if (!script || entry.cancelled) return [];
      const board = entry.board ? new LedBoard(entry.board, script.whistle, teams) : null;
      return [
        {
          entry,
          scene: new Scene(script, art.data, data.home),
          board,
          length: Math.max(script.duration, board?.length ?? 0),
        },
      ];
    });
  }, [animation.data, art.data]);

  // Following live, a new play plays after the one on screen; a backlog of more than three
  // skips ahead to the last three.
  useEffect(() => {
    if (!clips.length) return;
    if (live < 0) setLive(clips.length - 1);
    else if (clips.length - 1 - live > 3) setLive(clips.length - 3);
  }, [clips.length, live]);
  const target = Math.max(
    0,
    Math.min(index ?? (live >= 0 ? live : clips.length - 1), clips.length - 1),
  );
  // A new play, or a replay of the same one, starts its clock again.
  // biome-ignore lint/correctness/useExhaustiveDependencies: the clock restarts when these change
  useEffect(() => {
    clock.current = { started: performance.now(), frozen: 0 };
  }, [target, epoch]);

  const font = useMemo(() => getComputedStyle(document.body).fontFamily || "sans-serif", []);

  const drawAt = useCallback(
    (clip: Clip, t: number) => {
      const element = canvas.current;
      if (!element || !art.data) return;
      const ctx = element.getContext("2d");
      if (!ctx) return;
      const meta = art.data.meta;
      ctx.drawImage(art.data.field, 0, 0);
      if (clip.board) {
        const top = meta.board.top - meta.band.top;
        const image = clip.board.at(t);
        drawBoard(ctx, image, meta.camera.width, top, top + image.height + 16);
      }
      clip.scene.draw(ctx, t, font);
      const bar = meta.camera.caption_size + 21;
      const bottom = element.height;
      ctx.fillStyle = "rgba(10,12,14,0.894)";
      ctx.fillRect(0, bottom - bar, element.width, bar);
      ctx.textBaseline = "top";
      ctx.fillStyle = "rgb(240,240,235)";
      ctx.font = `${meta.camera.caption_size}px ${font}`;
      ctx.fillText(clip.scene.script.caption, 16, bottom - bar + 8, element.width - 560);
      const notes = [
        NOTE,
        ...Object.values(meta.labels).filter(Boolean),
        clip.entry.source === "espn" ? "Fallback source: ESPN" : null,
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
    [art.data, font],
  );

  // biome-ignore lint/correctness/useExhaustiveDependencies: a replay (epoch) redraws from the start
  useEffect(() => {
    if (!clips.length || target < 0) return;
    const clip = clips[target];
    let frame = 0;
    const tick = (now: number) => {
      const elapsed = paused ? clock.current.frozen : (now - clock.current.started) / 1000;
      const t = reduced ? clip.length : Math.min(elapsed, clip.length);
      drawAt(clip, t);
      if (reduced || paused) return;
      if (elapsed < clip.length) frame = requestAnimationFrame(tick);
      else if (index === null && target < clips.length - 1) setLive(target + 1);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [clips, target, reduced, paused, drawAt, index, epoch]);

  const togglePause = () => {
    if (!paused) clock.current.frozen = (performance.now() - clock.current.started) / 1000;
    else clock.current.started = performance.now() - clock.current.frozen * 1000;
    setPaused(!paused);
  };
  const go = (next: number | null) => {
    setPaused(false);
    setIndex(next === null ? null : Math.max(0, Math.min(clips.length - 1, next)));
    setEpoch((e) => e + 1);
  };
  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "k") togglePause();
    else if (event.key === "ArrowLeft") go(target - 1);
    else if (event.key === "ArrowRight") go(target + 1);
    else if (event.key === "r") go(target);
    else if (event.key === "l") go(null);
    else return;
    event.preventDefault();
  };

  if (animation.isPending) return null;
  if (animation.isError || !animation.data) return null;
  if (!animation.data.art.available) {
    return (
      <p className="live-field-note">
        The field for this game isn't ready: its art hasn't been built yet.
      </p>
    );
  }
  if (art.isError) return <p className="live-field-note">The field's art couldn't be loaded.</p>;
  if (!art.data) return null;
  if (!clips.length) return <EmptyField art={art.data} />;
  const meta = art.data.meta;
  const current = clips[Math.min(target, clips.length - 1)];
  return (
    <section className="live-field" aria-label="Live field">
      <button
        type="button"
        className="live-field-stage"
        onClick={togglePause}
        onKeyDown={onKey}
        aria-label={`Live field, ${paused ? "paused" : "playing"}. Press to ${paused ? "play" : "pause"}; arrow keys step between plays.`}
        aria-describedby="live-field-keys"
      >
        <canvas ref={canvas} width={meta.camera.width} height={meta.band.bottom - meta.band.top} />
      </button>
      <div className="live-field-controls">
        <button
          type="button"
          className="quiet"
          onClick={() => go(target - 1)}
          disabled={target <= 0}
        >
          Previous play
        </button>
        <button type="button" className="quiet" onClick={() => go(target)}>
          Replay
        </button>
        <button type="button" className="quiet" onClick={togglePause} aria-pressed={paused}>
          {paused ? "Play" : "Pause"}
        </button>
        <button
          type="button"
          className="quiet"
          onClick={() => go(target + 1)}
          disabled={target >= clips.length - 1}
        >
          Next play
        </button>
        <button
          type="button"
          className="quiet"
          onClick={() => go(null)}
          aria-pressed={index === null}
        >
          Live
        </button>
        <span className="live-field-now">
          {current.entry.period ? `Q${current.entry.period} ${current.entry.clock ?? ""}` : ""}{" "}
          {current.entry.part === "try" ? "· Try" : ""}
        </span>
      </div>
      <p id="live-field-keys" className="live-field-note">
        Keys on the field: Enter or space pauses, arrows step between plays, R replays, L follows
        the game live.
        {reduced ? " Motion is reduced: each play shows where it ended." : ""}
      </p>
    </section>
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
