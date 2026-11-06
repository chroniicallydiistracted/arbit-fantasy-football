// The live field's scene (OWN-042): one play script drawn at a moment, as the review renderer
// (scripts/sprites/preview.py) draws it, so the browser matches the clips the owner reviewed.
// The camera is the fixed full-field view (OWN-030). The field arrives pre-warped for it, and every
// sprite is painted by the server from the game's listed uniforms (OWN-028). Colors here are the
// art's own (sprite shadows, ball, lines and flags), not interface styling.
import type { components } from "../generated/api";

export type Script = components["schemas"]["PlayScript"];
type Actor = components["schemas"]["Actor"];
type Segment = components["schemas"]["Segment"];
type BallSegment = components["schemas"]["BallSegment"];
type BallEnd = components["schemas"]["BallEnd"];
type Vec = [number, number, number];

export type FrameInfo = {
  w: number;
  h: number;
  torso: number;
  near_hand: [number, number] | null;
  chest: [number, number] | null;
};
export type Meta = {
  event_id: string;
  camera: {
    width: number;
    height: number;
    rise: number;
    back: number;
    look: [number, number];
    focal: number;
    x: number;
    min_art: number;
    ball_radius: number;
    tag_size: number;
    caption_size: number;
  };
  band: { top: number; bottom: number };
  board: { top: number };
  art_pixel_yards: number;
  cycles: Record<string, { frames: string[]; step: number }>;
  frames: Record<string, FrameInfo>;
  ball_offsets: Record<string, [number, number]>;
  ball: { image: string; half: number; width: number };
  posts: { z: number; half: number; crossbar: number; top: number; at: number[] };
  officials: { image: string; rects: Record<string, [number, number, number, number]> };
  skin_sets: number[];
  teams: Record<
    "home" | "away",
    {
      code: string;
      sprites: { image: string; rects: Record<string, [number, number, number, number]> };
      tag: [number[], number[]];
      logo: number[][];
    }
  >;
  labels: Record<string, string | null>;
};
export type Art = {
  meta: Meta;
  field: HTMLImageElement;
  sprites: Record<string, HTMLImageElement>;
  officials: HTMLImageElement;
  ball: HTMLImageElement;
};

const LOS: [number, number, number, number] = [40, 110, 230, 215];
const TO_GAIN: [number, number, number, number] = [250, 215, 40, 225];
const POST_YELLOW = "rgb(250,210,40)";
const FLAG_YELLOW = "rgb(255,214,10)";
const FLAG_EDGE = "rgb(120,90,0)";
const BALL_FILL = "rgb(112,60,22)";
const BALL_EDGE = "rgb(20,10,4)";
const SHADOW = "rgba(0,0,0,0.333)";
const GRAVITY = 10.7;
const WOBBLE = (3 * Math.PI) / 180;
const TUMBLE = 2.0;

const sub = (a: Vec, b: Vec): Vec => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec, b: Vec) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec, b: Vec): Vec => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const norm = (a: Vec): Vec => {
  const length = Math.hypot(a[0], a[1], a[2]);
  return length > 1e-9 ? [a[0] / length, a[1] / length, a[2] / length] : [0, 0, 0];
};
const css = (c: number[]) =>
  c.length > 3 ? `rgba(${c[0]},${c[1]},${c[2]},${c[3] / 255})` : `rgb(${c[0]},${c[1]},${c[2]})`;

export class Camera {
  position: Vec;
  forward: Vec;
  right: Vec;
  up: Vec;
  constructor(readonly shot: Meta["camera"]) {
    this.position = [shot.x, shot.rise, -shot.back];
    this.forward = norm(sub([shot.x, shot.look[0], shot.look[1]], this.position));
    this.right = norm(cross([0, 1, 0], this.forward));
    this.up = cross(this.forward, this.right);
  }
  // Screen x, y on the full frame, and pixels per yard at that depth.
  project(x: number, y: number, z: number): [number, number, number] {
    const offset = sub([x, y, z], this.position);
    const depth = dot(offset, this.forward);
    const f = this.shot.focal;
    return [
      this.shot.width / 2 + (f * dot(offset, this.right)) / depth,
      this.shot.height / 2 - (f * dot(offset, this.up)) / depth,
      f / depth,
    ];
  }
}

// Where an actor is, what frame he shows and which way he faces at time t. A running cycle
// advances with the ground he has covered, so strides match his speed.
export function actorAt(actor: Actor, t: number, cycles: Meta["cycles"]) {
  const segments = actor.segments;
  let travel = 0;
  let index = segments.length - 1;
  for (let i = 0; i < segments.length; i += 1) {
    if (t < segments[i].end) {
      index = i;
      break;
    }
    travel += Math.hypot(segments[i].x1 - segments[i].x0, segments[i].z1 - segments[i].z0);
  }
  const seg: Segment = segments[index];
  const span = seg.end - seg.start;
  const share = t >= seg.end ? 1 : Math.max(0, Math.min(1, span > 0 ? (t - seg.start) / span : 1));
  const x = seg.x0 + (seg.x1 - seg.x0) * share;
  const z = seg.z0 + (seg.z1 - seg.z0) * share;
  travel += Math.hypot(x - seg.x0, z - seg.z0);
  let pose = seg.pose;
  const cycle = cycles[pose];
  if (cycle) pose = cycle.frames[Math.floor(travel / cycle.step) % cycle.frames.length];
  const facing = seg.facing ?? actor.facing;
  return { x, z, pose, base: seg.pose, left: facing === "left" };
}

// The flight of a pass, kick or snap: straight across the ground, an arc under gravity above it.
function flight(start: number, end: number, from: Vec, to: Vec) {
  const duration = end - start;
  const rise = (to[1] - from[1] + 0.5 * GRAVITY * duration * duration) / duration;
  return (t: number): Vec => {
    const elapsed = t - start;
    const share = elapsed / duration;
    return [
      from[0] + (to[0] - from[0]) * share,
      from[1] + rise * elapsed - 0.5 * GRAVITY * elapsed * elapsed,
      from[2] + (to[2] - from[2]) * share,
    ];
  };
}

type BallNow = { at: Vec; spin: string; since: number } | null;

export class Scene {
  camera: Camera;
  flights = new Map<number, (t: number) => Vec>();
  actors: Map<string, Actor>;
  // `home` is the home team's ESPN ID: a script names teams by ID.
  constructor(
    readonly script: Script,
    readonly art: Art,
    readonly home: string,
  ) {
    this.camera = new Camera(art.meta.camera);
    this.actors = new Map(script.actors.map((a) => [a.key, a]));
    script.ball.forEach((seg, index) => {
      if (seg.state === "flight" && seg.origin && seg.target) {
        this.flights.set(
          index,
          flight(
            seg.start,
            seg.end,
            this.point(seg.origin, seg.start),
            this.point(seg.target, seg.end - 1e-3),
          ),
        );
      }
    });
  }

  // A hand, chest or point, in field yards.
  point(end: BallEnd, t: number): Vec {
    if (end.point) return end.point as Vec;
    const actor = this.actors.get(end.actor ?? "");
    if (!actor) return [50, 1, 26.67];
    const now = actorAt(actor, t, this.art.meta.cycles);
    const frame = this.art.meta.cycles[now.base]?.frames[0] ?? now.base;
    const meta = this.art.meta;
    let dx = 0;
    let dy = 1;
    if ((end.hold ?? "hand") === "chest") {
      const info = meta.frames[frame];
      const chest = meta.frames[frame.replace(/_e$/, "")]?.chest ?? info?.chest;
      if (info && chest) {
        dx = (chest[0] - info.torso) * meta.art_pixel_yards;
        dy = (info.h - chest[1]) * meta.art_pixel_yards;
      }
    } else {
      const offset = meta.ball_offsets[frame];
      if (offset) [dx, dy] = offset;
    }
    return [now.x + (now.left ? -dx : dx), dy, now.z];
  }

  ball(t: number): BallNow {
    for (let i = 0; i < this.script.ball.length; i += 1) {
      const seg: BallSegment = this.script.ball[i];
      if (seg.start <= t && t < seg.end) {
        if (seg.state === "rest" && seg.at)
          return {
            at: seg.at as Vec,
            spin: seg.spin === "upright" ? "upright" : "flat",
            since: seg.start,
          };
        if (seg.state === "flight") {
          const at = this.flights.get(i);
          return at ? { at: at(t), spin: seg.spin, since: seg.start } : null;
        }
        return null; // held: drawn in the carrier's hands
      }
    }
    return null;
  }

  carrier(t: number): string | null {
    const held = this.script.ball.find(
      (seg) => seg.state === "held" && seg.start <= t && t < seg.end,
    );
    return held?.actor ?? null;
  }

  axis(t: number, now: NonNullable<BallNow>): Vec {
    if (now.spin === "upright") return [0, 1, 0];
    const step = 0.02;
    const before = this.ball(t - step);
    const after = this.ball(t + step);
    let velocity: Vec = [1, 0, 0];
    if (before && after && before.spin === now.spin && after.spin === now.spin)
      velocity = sub(after.at, before.at).map((v) => v / (2 * step)) as Vec;
    else if (after && after.spin === now.spin)
      velocity = sub(after.at, now.at).map((v) => v / step) as Vec;
    else if (before && before.spin === now.spin)
      velocity = sub(now.at, before.at).map((v) => v / step) as Vec;
    let heading = norm([velocity[0], 0, velocity[2]]);
    if (Math.hypot(...heading) < 1e-6) heading = [1, 0, 0];
    if (now.spin === "flat") return heading;
    if (now.spin === "tumble") {
      const turn = Math.PI / 2 + 2 * Math.PI * TUMBLE * (t - now.since);
      return [Math.cos(turn) * heading[0], Math.sin(turn), Math.cos(turn) * heading[2]];
    }
    const nose = Math.hypot(...velocity) > 1e-6 ? norm(velocity) : heading;
    let side = norm(cross(nose, [0, 1, 0]));
    if (Math.hypot(...side) < 1e-6) side = [0, 0, 1];
    const lift = cross(side, nose);
    const circle = 2 * Math.PI * 3 * t;
    const k = Math.tan(WOBBLE);
    return norm(
      [0, 1, 2].map(
        (i) => nose[i] + k * (Math.cos(circle) * side[i] + Math.sin(circle) * lift[i]),
      ) as Vec,
    );
  }

  // Draw the moment t into a canvas the size of the band (the full frame from band.top).
  draw(ctx: CanvasRenderingContext2D, t: number, tagFont: string) {
    const { meta } = this.art;
    const top = meta.band.top;
    const cam = this.camera;
    const P = (x: number, y: number, z: number) => {
      const [sx, sy, k] = cam.project(x, y, z);
      return [sx, sy - top, k] as [number, number, number];
    };
    ctx.imageSmoothingEnabled = false;
    for (const line of this.script.lines) {
      const color = line.kind === "scrimmage" ? LOS : TO_GAIN;
      ctx.fillStyle = css(color);
      ctx.beginPath();
      [
        [line.x - 0.28, 0],
        [line.x + 0.28, 0],
        [line.x + 0.28, 53.3],
        [line.x - 0.28, 53.3],
      ].forEach(([a, b], i) => {
        const [sx, sy] = P(a, 0, b);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      });
      ctx.closePath();
      ctx.fill();
    }
    this.drawFlags(ctx, t, P);

    type Item = { z: number; order: number; draw: () => void };
    const items: Item[] = [];
    const tags: { x: number; y: number; text: string; colors: [number[], number[]] | null }[] = [];
    const carrier = this.carrier(t);
    for (const actor of this.script.actors) {
      const now = actorAt(actor, t, meta.cycles);
      items.push({
        z: now.z,
        order: 0,
        draw: () => this.drawActor(ctx, actor, now, P, tags, carrier === actor.key),
      });
    }
    for (const at of meta.posts.at) {
      for (const [z, piece] of this.posts(at, P))
        items.push({ z, order: 0, draw: () => piece(ctx) });
    }
    const ball = this.ball(t);
    if (ball) items.push({ z: ball.at[2], order: 1, draw: () => this.drawBall(ctx, t, ball, P) });
    items.sort((a, b) => b.z - a.z || a.order - b.order);
    for (const item of items) item.draw();
    this.drawTags(ctx, tags, tagFont);
  }

  private drawActor(
    ctx: CanvasRenderingContext2D,
    actor: Actor,
    now: ReturnType<typeof actorAt>,
    P: (x: number, y: number, z: number) => [number, number, number],
    tags: { x: number; y: number; text: string; colors: [number[], number[]] | null }[],
    carrying: boolean,
  ) {
    const { meta } = this.art;
    const info = meta.frames[now.pose];
    if (!info) return;
    const official = actor.side === "official";
    const team = official
      ? null
      : actor.side === "offense"
        ? this.script.offense
        : this.script.defense;
    const side = team === null || team === undefined ? null : team === this.home ? "home" : "away";
    const identity = actor.espn_id
      ? Number(actor.espn_id)
      : [...(actor.label ?? actor.key)].reduce((s, c) => s + c.charCodeAt(0), 0);
    const skin = meta.skin_sets[identity % 2];
    const sheet = official ? this.art.officials : this.art.sprites[side ?? "home"];
    const rect = official
      ? meta.officials.rects[now.pose]
      : meta.teams[side ?? "home"].sprites.rects[`${now.pose}|${skin}`];
    if (!rect) return;
    const [sx, sy, perYard] = P(now.x, 0, now.z);
    const art = Math.max(meta.camera.min_art, perYard * meta.art_pixel_yards);
    const w = Math.max(1, Math.round(rect[2] * art));
    const h = Math.max(1, Math.round(rect[3] * art));
    const anchor = now.left ? rect[2] - info.torso : info.torso;
    ctx.fillStyle = SHADOW;
    ctx.beginPath();
    ctx.ellipse(sx, sy - perYard * 0.01, w * 0.42, perYard * 0.21, 0, 0, Math.PI * 2);
    ctx.fill();
    const left = Math.round(sx - anchor * art);
    const top = Math.round(sy - h);
    ctx.save();
    if (now.left) {
      ctx.translate(left + w, top);
      ctx.scale(-1, 1);
      ctx.drawImage(sheet, rect[0], rect[1], rect[2], rect[3], 0, 0, w, h);
    } else {
      ctx.drawImage(sheet, rect[0], rect[1], rect[2], rect[3], left, top, w, h);
    }
    ctx.restore();
    if (actor.label)
      tags.push({
        x: sx,
        y: sy - h - 6,
        text: actor.label,
        colors: side ? meta.teams[side].tag : null,
      });
    const base = now.pose.replace(/_e$/, "");
    const anchors = meta.frames[base];
    if (carrying && anchors) {
      const held = /^(throw|punt|handoff)/.test(now.pose) ? anchors.near_hand : anchors.chest;
      if (held) {
        const hand = now.left ? rect[2] - held[0] : held[0];
        const bw = Math.max(1, Math.round(this.art.ball.width * art));
        const bh = Math.max(1, Math.round(this.art.ball.height * art));
        ctx.drawImage(
          this.art.ball,
          Math.round(sx - anchor * art + hand * art - bw / 2),
          Math.round(top + held[1] * art - bh / 2),
          bw,
          bh,
        );
      }
    }
  }

  private drawBall(
    ctx: CanvasRenderingContext2D,
    t: number,
    ball: NonNullable<BallNow>,
    P: (x: number, y: number, z: number) => [number, number, number],
  ) {
    const meta = this.art.meta;
    const least = meta.camera.ball_radius;
    const [gx, gy, gk] = P(ball.at[0], 0, ball.at[2]);
    const shadow = Math.max(gk * 0.2, least * 0.8);
    ctx.fillStyle = "rgba(0,0,0,0.31)";
    ctx.beginPath();
    ctx.ellipse(gx, gy, shadow, shadow * 0.4, 0, 0, Math.PI * 2);
    ctx.fill();
    const [x, y, k] = P(...ball.at);
    const radius = Math.max(k * meta.ball.half, least);
    const axis = this.axis(t, ball);
    const [nx, ny] = P(
      ball.at[0] + axis[0] * meta.ball.half,
      ball.at[1] + axis[1] * meta.ball.half,
      ball.at[2] + axis[2] * meta.ball.half,
    );
    const scale = radius / (k * meta.ball.half);
    const reach = [(nx - x) * scale, (ny - y) * scale];
    const length = Math.hypot(reach[0], reach[1]);
    const along = length > 1e-6 ? [reach[0] / length, reach[1] / length] : [1, 0];
    const across = [-along[1], along[0]];
    const major = Math.max(length, radius * meta.ball.width);
    const minor = radius * meta.ball.width;
    ctx.beginPath();
    for (let i = 0; i <= 16; i += 1) {
      const a = (i / 16) * Math.PI * 2;
      const px = x + Math.cos(a) * major * along[0] + Math.sin(a) * minor * across[0];
      const py = y + Math.cos(a) * major * along[1] + Math.sin(a) * minor * across[1];
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.fillStyle = BALL_FILL;
    ctx.fill();
    ctx.strokeStyle = BALL_EDGE;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Goalposts as pieces with their depth, so a good kick passes behind the near upright.
  private posts(
    x: number,
    P: (x: number, y: number, z: number) => [number, number, number],
  ): [number, (ctx: CanvasRenderingContext2D) => void][] {
    const { z, half, crossbar, top } = this.art.meta.posts;
    const near = z - half;
    const far = z + half;
    const piece =
      (a: Vec, b: Vec, thickness: number, at: Vec) => (ctx: CanvasRenderingContext2D) => {
        const [, , k] = P(...at);
        const [ax, ay] = P(...a);
        const [bx, by] = P(...b);
        ctx.strokeStyle = POST_YELLOW;
        ctx.lineWidth = Math.max(2, Math.round(k * thickness));
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      };
    const base: Vec = [x, 0, z];
    const bar: Vec = [x, crossbar, z];
    return [
      [z, piece(base, bar, 0.18, base)],
      [z, piece([x, crossbar, near], [x, crossbar, far], 0.14, bar)],
      [near, piece([x, crossbar, near], [x, top, near], 0.12, [x, crossbar, near])],
      [far, piece([x, crossbar, far], [x, top, far], 0.12, [x, crossbar, far])],
    ];
  }

  private drawFlags(
    ctx: CanvasRenderingContext2D,
    t: number,
    P: (x: number, y: number, z: number) => [number, number, number],
  ) {
    for (const prop of this.script.props ?? []) {
      if (t < prop.start) continue;
      let x: number;
      let y: number;
      let z: number;
      if (t < prop.land) {
        const share = (t - prop.start) / (prop.land - prop.start);
        x = prop.origin[0] + (prop.at[0] - prop.origin[0]) * share;
        z = prop.origin[2] + (prop.at[2] - prop.origin[2]) * share;
        y = prop.origin[1] * (1 - share) + 2.5 * Math.sin(Math.PI * share);
      } else {
        [x, y, z] = prop.at as Vec;
      }
      const [sx, sy, k] = P(x, y, z);
      const half = Math.max(3, k * 0.32);
      ctx.fillStyle = FLAG_YELLOW;
      ctx.strokeStyle = FLAG_EDGE;
      ctx.lineWidth = 1;
      ctx.beginPath();
      if (t < prop.land) {
        const turn = 4 * Math.PI * (t - prop.start);
        for (let i = 0; i < 4; i += 1) {
          const a = turn + (i * Math.PI) / 2;
          if (i === 0) ctx.moveTo(sx + half * Math.cos(a), sy + half * Math.sin(a));
          else ctx.lineTo(sx + half * Math.cos(a), sy + half * Math.sin(a));
        }
        ctx.closePath();
      } else {
        ctx.ellipse(sx, sy, half * 1.3, half * 0.45, 0, 0, Math.PI * 2);
      }
      ctx.fill();
      ctx.stroke();
    }
  }

  // Name tags in the owner's style C (OWN-037): team color, a second-color shadow, no box. A later
  // tag moves up above an earlier one so players who meet keep their names readable.
  private drawTags(
    ctx: CanvasRenderingContext2D,
    tags: { x: number; y: number; text: string; colors: [number[], number[]] | null }[],
    font: string,
  ) {
    const size = this.art.meta.camera.tag_size;
    ctx.font = `${size}px ${font}`;
    ctx.textBaseline = "top";
    const height = size + 4;
    const boxes: [number, number, number, number][] = [];
    for (const tag of [...tags].sort((a, b) => b.y - a.y)) {
      const half = ctx.measureText(tag.text).width / 2 + 4;
      let y = tag.y;
      while (
        boxes.some(
          ([l, t, r, b]) => tag.x - half < r && l < tag.x + half && y - height < b && t < y,
        )
      )
        y -= 1;
      boxes.push([tag.x - half, y - height, tag.x + half, y]);
      if (tag.colors) {
        ctx.fillStyle = css(tag.colors[1]);
        ctx.fillText(tag.text, tag.x - half + 5, y - height + 2);
        ctx.fillStyle = css(tag.colors[0]);
        ctx.fillText(tag.text, tag.x - half + 4, y - height + 1);
      } else {
        ctx.fillStyle = "rgba(10,12,14,0.67)";
        ctx.fillRect(tag.x - half, y - height, half * 2, height);
        ctx.fillStyle = "rgb(240,240,235)";
        ctx.fillText(tag.text, tag.x - half + 4, y - height + 1);
      }
    }
  }
}
