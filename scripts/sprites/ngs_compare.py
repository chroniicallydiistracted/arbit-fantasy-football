"""Compare our re-creation of a play with the play's real NGS tracking, as a reference only.

The owner supplies NGS highlight files privately (Q-011): they show how a play really happened,
so the choreographer can be judged against it. They are never a live source and never leave
ignored data/. For each file this renders two clips with the same review renderer, field and kits:

- **ours:** the play as the app builds it today (`animation.build`, from the stored NFL plays).
- **ngs:** the same play from the tracking: every relevant player where he really was each tenth
  of a second, and the ball's real holders and flights. Poses come from speed (running, standing),
  with the throw, catch, fall and ground at the real events.

Relevant players are the ones the play involves: everyone in the NFL's play stats or named in the
description, the center on a scrimmage play and the quarterback on a handoff. Both clips start
0.6 s before the snap (a kickoff is aligned on the kick), so they can be stacked and compared.
A summary of event times, alignment and speeds is written beside the clips.

Usage:
  uv run --offline --env-file .env.local python scripts/sprites/ngs_compare.py \\
      --event 401873037 --field FIELD.png --uniform 33=SHEET --uniform 30=SHEET NGS.json ...
"""

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import preview as P  # noqa: E402
import render_script as RS  # noqa: E402
import uniforms as U  # noqa: E402
from arbit_data.db import UnitOfWork  # noqa: E402
from arbit_data.live import animation  # noqa: E402
from arbit_data.live.choreography import (  # noqa: E402
    SNAP,
    Actor,
    BallEnd,
    BallSegment,
    PlayScript,
    Segment,
)
from arbit_data.live.nfl_feed import gsis_to_espn  # noqa: E402

OUT = ROOT / "data/sprites/review/ngs-compare-2026-11-07"
WIDTH = 53.33
RUNNING = 2.5  # yards a second: faster than this he is running
HELD = 1.3  # yards: the ball this close to a player is in his hands
KEEP = 1.9  # yards: the holder keeps it while it stays this close


def when(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def short(player: dict) -> str:
    return f"{player['firstName'][:1]}.{player['lastName']}"


class Frame:
    """The NGS field turned into the script's: the offense goes toward +x from its line of
    scrimmage, and its right hand is +z, as the choreographer draws it."""

    def __init__(self, play: dict, los: float):
        self.right = play["playDirection"] == "right"
        self.at = float(play["absoluteYardlineNumber"])
        self.los = los

    def __call__(self, x: float, y: float) -> tuple[float, float]:
        sign = 1 if self.right else -1
        return self.los + sign * (x - self.at), (WIDTH - y) if self.right else y


def relevant(ngs: dict) -> list[dict]:
    play = ngs["play"]
    players = [*ngs["homeTrackingData"], *ngs["awayTrackingData"]]
    stats = {s["gsisId"] for s in play.get("playStats", []) if s.get("gsisId")}
    text = play["playDescription"]
    offense = play["possessionTeamId"]
    home = ngs["schedule"]["homeTeamId"]
    chosen = []
    for p in players:
        team = home if p in ngs["homeTrackingData"] else ngs["schedule"]["visitorTeamId"]
        named = re.search(rf"\b{re.escape(short(p))}\b", text) is not None
        center = p["position"] == "C" and team == offense and play["playType"] != "play_type_kickoff"
        handoff = p["position"] == "QB" and team == offense and play["playType"] == "play_type_rush"
        if p["gsisId"] in stats or named or center or handoff:
            chosen.append({**p, "offense": team == offense})
    return chosen


def ngs_script(ngs: dict, ours: PlayScript, espn: dict[str, str]) -> tuple[PlayScript, dict]:
    play = ngs["play"]
    events = {e["name"]: when(e["time"]) for e in ngs["events"]}
    kickoff = play["playType"] == "play_type_kickoff"
    if kickoff:
        kick = events["kickoff"]
        ours_kick = next((b.start for b in ours.ball if b.state == "flight"), 1.7)
        zero = kick - ours_kick
    else:
        zero = events["ball_snap"] - SNAP
    end = when(ngs["submittedPlay"]["playEnd"]) - zero
    duration = round(end + 1.6, 3)
    to = Frame(play, next(line.x for line in ours.lines if line.kind == "scrimmage"))
    players = relevant(ngs)

    def track(p: dict) -> list[tuple[float, float, float]]:
        out = []
        for s in p["playerTrackingData"]:
            t = when(s["time"]) - zero
            if -0.05 <= t <= duration + 0.05:
                out.append((round(max(0.0, t), 3), *to(s["x"], s["y"])))
        return out

    tracks = {p["gsisId"]: track(p) for p in players}
    keys = {}
    for p in players:
        base = re.sub(r"[^a-z]", "", p["lastName"].lower()) or "player"
        keys[p["gsisId"]] = base if base not in keys.values() else f"{base}_{p['jerseyNumber']}"

    def where(gsis: str, t: float) -> tuple[float, float]:
        samples = tracks[gsis]
        for (t0, x0, z0), (t1, x1, z1) in zip(samples, samples[1:], strict=False):
            if t0 <= t <= t1:
                share = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                return x0 + (x1 - x0) * share, z0 + (z1 - z0) * share
        last = samples[-1] if t > samples[-1][0] else samples[0]
        return last[1], last[2]

    # Who has the ball each time it is tracked: the nearest relevant player of the side in
    # possession, kept while close. The offense has it until an interception or a received kick
    # gives it to the other side, so a defender draped on a receiver never takes it.
    offense_of = {p["gsisId"]: p["offense"] for p in players}
    switch = min(
        (events[k] - zero for k in ("pass_outcome_interception", "kick_received", "punt_received") if k in events),
        default=math.inf,
    )

    def allowed(g: str, t: float) -> bool:
        return offense_of[g] == (t < switch - 0.3)

    ball_track = [(when(b["time"]) - zero, *to(b["x"], b["y"])) for b in ngs["ballTrackingData"]]
    ball_track = [b for b in ball_track if 0 <= b[0] <= duration]
    start = SNAP if not kickoff else ball_track[0][0]
    holders: list[tuple[float, str | None, float, float]] = []
    current: str | None = None
    for t, x, z in ball_track:
        if t < (events["kickoff"] - zero if kickoff else SNAP):
            holders.append((t, None, x, z))
            continue
        near = sorted(
            (math.hypot(x - px, z - pz), g) for g in tracks if allowed(g, t) for px, pz in [where(g, t)]
        )
        if current and allowed(current, t) and math.hypot(x - where(current, t)[0], z - where(current, t)[1]) <= KEEP:
            pass
        elif near and near[0][0] <= HELD:
            current = near[0][1]
        else:
            current = None
        holders.append((t, current, x, z))

    ball: list[BallSegment] = []
    first = holders[0] if holders else (0.0, None, to.los, to(0, 0)[1])
    rest_until = next((t for t, g, *_ in holders if g is not None), duration)
    ball.append(BallSegment(start=0.0, end=round(min(start, rest_until), 3), state="rest", at=(first[2], 0.15, first[3])))
    runs: list[list] = []
    for t, g, x, z in holders:
        if g is None:
            continue
        if runs and runs[-1][0] == g:
            runs[-1][2] = t
        else:
            runs.append([g, t, t])
    # A hold shorter than 0.35 s between two others is the ball passing a player, such as a
    # defender in coverage at the catch, not a catch.
    runs = [r for i, r in enumerate(runs) if i in (0, len(runs) - 1) or r[2] - r[1] >= 0.35]
    merged: list[list] = []
    for r in runs:
        if merged and merged[-1][0] == r[0]:
            merged[-1][2] = r[2]
        else:
            merged.append(r)
    runs = merged
    previous_end, previous = ball[-1].end, None
    for g, t0, t1 in runs:
        if t0 - previous_end > 0.05:
            origin = BallEnd(actor=keys[previous], hold="hand") if previous else BallEnd(point=(first[2], 0.3, first[3]))
            ball.append(BallSegment(start=round(previous_end, 3), end=round(t0, 3), state="flight", origin=origin, target=BallEnd(actor=keys[g], hold="hands")))
        ball.append(BallSegment(start=round(max(t0, previous_end), 3), end=round(t1 + 0.1, 3), state="held", actor=keys[g]))
        previous_end, previous = round(t1 + 0.1, 3), g
    if ball[-1].state == "held":
        ball[-1] = ball[-1].model_copy(update={"end": duration})

    # Each player's moves, a tenth of a second at a time, posed from his speed and the events.
    carrier_end = runs[-1][0] if runs else None
    thrower = runs[0][0] if runs and "pass_forward" in events else None
    throw_at = events.get("pass_forward", 0) - zero
    catch_at = next((events[k] - zero for k in ("pass_outcome_caught", "pass_outcome_interception", "kick_received") if k in events), None)
    catcher = next((g for g, t0, _ in runs if catch_at is not None and t0 >= catch_at - 0.6), None)
    down_at = events.get("tackle", 0) - zero if "tackle" in events else None
    actors = []
    for p in players:
        g = p["gsisId"]
        samples = tracks[g]
        segments = []
        facing = "right" if p["offense"] else "left"
        for (t0, x0, z0), (t1, x1, z1) in zip(samples, samples[1:], strict=False):
            speed = math.hypot(x1 - x0, z1 - z0) / (t1 - t0) if t1 > t0 else 0.0
            if speed >= RUNNING and abs(x1 - x0) > 0.05:
                facing = "right" if x1 > x0 else "left"
            pose = "RUN" if speed >= RUNNING else ("stance_1" if t1 <= SNAP and not kickoff else "stand")
            if g == thrower and throw_at - 0.4 <= t0 < throw_at + 0.5:
                pose = ("throw_cock", "throw_mid", "throw_rel", "throw_follow")[min(3, max(0, int((t0 - throw_at + 0.4) / 0.2)))]
            if g == catcher and catch_at is not None and catch_at - 0.3 <= t0 < catch_at:
                pose = "catch_reach"
            if g == carrier_end and down_at is not None and t0 >= down_at - 0.2:
                pose = "fall_60" if t0 < down_at else "ground"
            segments.append(Segment(start=t0, end=t1, pose=pose, x0=round(x0, 3), z0=round(z0, 3), x1=round(x1, 3), z1=round(z1, 3), facing=facing))
        if not segments:
            continue
        if segments[0].start > 0:
            s0 = segments[0]
            segments.insert(0, s0.model_copy(update={"start": 0.0, "end": s0.start, "x1": s0.x0, "z1": s0.z0, "pose": "stance_1" if not kickoff else "stand"}))
        last = segments[-1]
        if last.end < duration:
            segments.append(last.model_copy(update={"start": last.end, "end": duration, "x0": last.x1, "z0": last.z1, "pose": "ground" if last.pose == "ground" else "stand"}))
        role = "carrier" if g == carrier_end else "player"
        actors.append(Actor(key=keys[g], espn_id=espn.get(g), role=role, side="offense" if p["offense"] else "defense", label=short(p), position=p["position"], facing="right" if p["offense"] else "left", segments=tuple(segments)))
    script = PlayScript(
        event_id=ours.event_id,
        provider_id=ours.provider_id,
        seed="ngs",
        template=ours.template,
        duration=duration,
        whistle=round(end, 3),
        offense=ours.offense,
        defense=ours.defense,
        actors=tuple(actors),
        ball=tuple(ball),
        lines=ours.lines,
        caption="NGS tracking · " + ours.caption,
    )
    facts = {
        "events": {k: round(v - zero, 2) for k, v in events.items() if v - zero >= -1 and k not in ("play_submit",)},
        "holders": [(keys[g], round(t0, 2), round(t1, 2)) for g, t0, t1 in runs],
        "players": {keys[p["gsisId"]]: {"name": short(p), "position": p["position"], "espn_id": espn.get(p["gsisId"])} for p in players},
    }
    return script, facts


def summary(script: PlayScript) -> dict:
    """Times and places a reviewer compares: when the ball changes hands, where everyone starts, how fast they go."""
    out = {"whistle": round(script.whistle - SNAP, 2), "ball": [], "players": {}}
    for b in script.ball:
        if b.state != "rest":
            out["ball"].append((b.state, b.actor or (b.target.actor if b.target else None), round(b.start - SNAP, 2)))
    los = next(line.x for line in script.lines if line.kind == "scrimmage")
    for a in script.actors:
        if a.side == "official":
            continue
        snap_at = next((s for s in a.segments if s.end > SNAP), a.segments[0])
        speeds = [math.hypot(s.x1 - s.x0, s.z1 - s.z0) / (s.end - s.start) for s in a.segments if s.end - s.start > 0.05]
        path = sum(math.hypot(s.x1 - s.x0, s.z1 - s.z0) for s in a.segments if s.start >= SNAP - 1e-6)
        out["players"][a.label or a.key] = {
            "at snap": (round(snap_at.x0 - los, 1), round(snap_at.z0, 1)),
            "end": (round(a.segments[-1].x1 - los, 1), round(a.segments[-1].z1, 1)),
            "top speed": round(max(speeds, default=0.0), 1),
            "path yards": round(path, 1),
        }
    return out


def stack(top: Path, bottom: Path, target: Path) -> None:
    """Ours above the tracking, frame for frame, at two-thirds size."""
    a, b = Image.open(top), Image.open(bottom)
    frames, durations = [], []
    count = max(a.n_frames, b.n_frames)
    for i in range(count):
        a.seek(min(i, a.n_frames - 1))
        b.seek(min(i, b.n_frames - 1))
        ta, tb = a.convert("RGB"), b.convert("RGB")
        w = int(ta.width * 2 / 3)
        ta = ta.resize((w, int(ta.height * w / ta.width)), Image.LANCZOS)
        tb = tb.resize((w, int(tb.height * w / tb.width)), Image.LANCZOS)
        sheet = Image.new("RGB", (w, ta.height + tb.height + 4))
        sheet.paste(ta, (0, 0))
        sheet.paste(tb, (0, ta.height + 4))
        d = ImageDraw.Draw(sheet)
        for y, text in ((4, "OURS: today's choreographer"), (ta.height + 8, "NGS: real positions and timing")):
            d.rectangle((6, y, 12 + 7 * len(text), y + 16), fill=(10, 12, 14))
            d.text((10, y + 2), text, fill=(250, 215, 40))
        frames.append(sheet)
        durations.append(a.info.get("duration", 40))
    sample = frames[:: max(1, len(frames) // 12)]
    montage = Image.new("RGB", (sample[0].width, sample[0].height * len(sample)))
    for i, im in enumerate(sample):
        montage.paste(im, (0, i * im.height))
    palette = montage.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    quantized = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    quantized[0].save(target, save_all=True, append_images=quantized[1:], duration=durations, loop=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--event", required=True)
    parser.add_argument("--field", type=Path, required=True)
    parser.add_argument("--uniform", action="append", default=[], help="ESPN team ID=Gridiron sheet")
    parser.add_argument("--code", action="append", default=[], help="ESPN team ID=nflverse code")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    P.FIELD = Image.open(args.field).convert("RGB").resize((1024 * P.SCALE, 486 * P.SCALE), Image.LANCZOS)
    P.SHOT, P.OUT = P.WIDE, args.out
    RS.UNIFORMS = {k: U.measure_file(Path(v)) for k, v in (u.split("=", 1) for u in args.uniform)}
    RS.CODES = dict(c.split("=", 1) for c in args.code)
    RS.TAGS = RS.tag_colors()
    uow = UnitOfWork(create_engine(os.environ["ARBIT_DATABASE_URL"]))
    espn = gsis_to_espn(uow)
    made = animation.build(uow, args.event)
    assert made is not None
    entries = {(e["play_id"], e["part"]): e for e in made["entries"]}
    report = {}
    for path in args.files:
        ngs = json.loads(path.read_text())
        number = str(ngs["play"]["playId"])
        entry = entries[(args.event + number, "play")]
        ours = entry["script"]
        truth, facts = ngs_script(ngs, ours, espn)
        RS.draw(ours, f"{number}-ours", entry["board"])
        RS.draw(truth, f"{number}-ngs", None)
        stack(args.out / f"play-{number}-ours.gif", args.out / f"play-{number}-ngs.gif", args.out / f"{number}-compare.gif")
        report[number] = {"text": ngs["play"]["playDescription"], "ours": summary(ours), "ngs": summary(truth), "ngs facts": facts}
        print(number, "done", flush=True)
    (args.out / "summary.json").write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
