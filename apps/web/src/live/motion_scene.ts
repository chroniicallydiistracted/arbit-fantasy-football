// Evaluates the replacement script using the same camera, art and field surfaces as member playback.
import type { components } from "../generated/api";
import { type ActorNow, type Art, type BallNow, Scene, spritePlacement, type Vec } from "./scene";

type Actor = components["schemas"]["Actor"];
type Body = components["schemas"]["MotionActor"];
type MotionKey = components["schemas"]["MotionKey"];
type Endpoint = components["schemas"]["BallEnd"];
type Ball = components["schemas"]["MotionBall"];
type Arc = { from: Vec; to: Vec; rise: number };
export type MotionScript = components["schemas"]["PlayScriptV2"];

function cubic(a: number, b: number, va: number, vb: number, u: number, span: number) {
  const c1 = span * va;
  const c2 = 3 * (b - a) - span * (2 * va + vb);
  const c3 = 2 * (a - b) + span * (va + vb);
  return a + u * (c1 + u * (c2 + u * c3));
}

function bodyAt(body: Body, t: number, cycles: Art["meta"]["cycles"]): ActorNow {
  const { track } = body;
  const next = track.findIndex((key) => key.t > t);
  let key: MotionKey;
  let distance = 0;
  const i = next < 0 ? track.length - 1 : Math.max(0, next - 1);
  for (let j = 1; j <= i; j += 1) {
    distance += Math.hypot(track[j].x - track[j - 1].x, track[j].z - track[j - 1].z);
  }
  const a = track[i];
  if (next <= 0) {
    key = a;
  } else {
    const b = track[next];
    const span = b.t - a.t;
    const u = (t - a.t) / span;
    const turn = b.heading - a.heading;
    key = {
      ...a,
      x: cubic(a.x, b.x, a.vx, b.vx, u, span),
      z: cubic(a.z, b.z, a.vz, b.vz, u, span),
      heading: a.heading + Math.atan2(Math.sin(turn), Math.cos(turn)) * (u * u * (3 - 2 * u)),
    };
    distance += Math.hypot(key.x - a.x, key.z - a.z);
  }
  let base = body.poses[0].pose;
  for (const cue of body.poses) {
    if (cue.start > t) break;
    base = cue.pose;
  }
  const cycle = cycles[base];
  const pose = cycle ? cycle.frames[Math.floor(distance / cycle.step) % cycle.frames.length] : base;
  const facing = Math.cos(key.heading);
  return {
    x: key.x,
    z: key.z,
    pose,
    base,
    left: facing < 0,
    widthScale: 0.73 + 0.27 * Math.abs(facing),
  };
}

export class MotionScene extends Scene {
  private bodies: Map<string, Body>;
  private arcs: (Arc | null)[];

  constructor(
    readonly motion: MotionScript,
    art: Art,
    home: string,
  ) {
    super(
      {
        ...motion,
        version: 1,
        seed: motion.provider_id,
        actors: motion.actors.map((actor) => ({
          key: actor.key,
          espn_id: actor.espn_id ?? null,
          role: actor.role,
          side: actor.side,
          label: actor.label,
          facing: "right",
          segments: [],
        })),
        ball: [],
        props: [],
      },
      art,
      home,
    );
    this.bodies = new Map(motion.actors.map((actor) => [actor.key, actor]));
    this.arcs = motion.ball.map((cue) => {
      if (!cue.target) return null;
      const a = this.attachment(cue.origin, cue.start);
      const b = this.attachment(cue.target, cue.end);
      return a && b ? { from: a.at, to: b.at, rise: this.arcRise(cue, a.at, b.at) } : null;
    });
  }

  protected override stateAt(actor: Actor, t: number): ActorNow {
    const body = this.bodies.get(actor.key);
    if (!body) throw new Error("Missing motion actor");
    return bodyAt(body, t, this.art.meta.cycles);
  }

  private attachment(endpoint: Endpoint, t: number): { at: Vec; depth: number } | null {
    if (endpoint.point) return { at: endpoint.point, depth: endpoint.point[2] };
    const body = this.bodies.get(endpoint.actor ?? "");
    if (!body) return null;
    const { meta } = this.art;
    const now = bodyAt(body, t, meta.cycles);
    const frame = meta.frames[now.pose];
    if (!frame) return null;
    const anchor = endpoint.hold === "chest" ? frame.chest : frame.near_hand;
    if (!anchor) return null;
    const [sx, sy, k] = this.camera.project(now.x, 0, now.z);
    const { left, top, w, scaleX, scaleY } = spritePlacement(meta, now, frame, sx, sy, k);
    const dx = (left + (now.left ? w - anchor[0] * scaleX : anchor[0] * scaleX) - sx) / k;
    const dy = (sy - top - anchor[1] * scaleY) / k;
    const { right, up } = this.camera;
    return {
      at: [
        now.x + right[0] * dx + up[0] * dy,
        right[1] * dx + up[1] * dy,
        now.z + right[2] * dx + up[2] * dy,
      ],
      depth: now.z,
    };
  }

  override ball(time: number): BallNow {
    const t = Math.min(time, this.motion.duration - 1e-6);
    const index = this.motion.ball.findIndex((cue) => cue.start <= t && t < cue.end);
    if (index < 0) return null;
    const cue = this.motion.ball[index];
    if (cue.style === "held" || cue.style === "rest") {
      const attached = this.attachment(cue.origin, t);
      return attached && { ...attached, spin: "flat", since: cue.start };
    }
    const arc = this.arcs[index];
    return arc ? this.flightAt(cue, arc, t) : null;
  }

  private arcRise(cue: Ball, from: Vec, to: Vec) {
    const duration = cue.end - cue.start;
    const natural = {
      snap: 0.12,
      exchange: 0.05,
      pass: 1.34 * duration * duration,
      kick: 1.34 * duration * duration,
      bounce: 0.7,
      roll: 0,
      rest: 0,
      held: 0,
    }[cue.style];
    const { band, camera: shot } = this.art.meta;
    const top = band.top + Math.max(6, shot.ball_radius ?? 0) + 2;
    const limit = (shot.height / 2 - top) / shot.focal;
    const up = this.camera.up[1] - limit * this.camera.forward[1];
    if (up <= 0 || natural === 0) return natural;
    const margin = (point: Vec) => {
      const [, y, scale] = this.camera.project(...point);
      return Math.max(0, (y - top) / scale);
    };
    // The projection boundary is a plane. Clearance along the flat flight varies
    // linearly, so this is the largest quadratic arc that stays below that plane.
    const visible = (Math.sqrt(margin(from)) + Math.sqrt(margin(to))) ** 2 / (4 * up);
    return Math.min(natural, visible);
  }

  private flightAt(cue: Ball, { from: a, to: b, rise }: Arc, t: number): NonNullable<BallNow> {
    const u = (t - cue.start) / (cue.end - cue.start);
    const travel = cue.style === "roll" ? u * (2 - u) : u;
    return {
      at: [
        a[0] + travel * (b[0] - a[0]),
        a[1] + u * (b[1] - a[1]) + rise * 4 * u * (1 - u),
        a[2] + travel * (b[2] - a[2]),
      ],
      spin:
        cue.style === "kick" || cue.style === "bounce"
          ? "tumble"
          : cue.style === "pass" || cue.style === "snap"
            ? "spiral"
            : "flat",
      since: cue.start,
    };
  }
}
