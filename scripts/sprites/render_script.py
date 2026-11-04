"""Render generated play scripts with the review renderer (automation slice 2 evidence).

Builds CHI at SEA (2026-11-02, event 401873036) from the private captures: each play is normalized,
interpreted (`play_facts`), choreographed (`choreography`) and drawn in the full-field view with the
uniforms and field Gridiron lists for that game, the same as `real_plays.py`. Scripts are written
next to the GIFs as JSON. Output stays in ignored data/ because it uses Gridiron art (OWN-015).

Usage:
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py [play ID suffix ...]
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py --compare
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py --all

With no plays it lists what can be rendered. --compare renders the five plays that real_plays.py
re-creates by hand, so the two can be watched side by side. Name tags come from the stored 2026
nflverse roster by ESPN ID; a player missing from it is named from the text only when that is
unambiguous.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import play_facts_coverage as coverage  # noqa: E402
import preview as P  # noqa: E402
import real_plays as R  # noqa: E402  (loads the game's field and measured uniforms)
from arbit_data.league import content_hash  # noqa: E402
from arbit_data.live.choreography import PlayScript, choreograph  # noqa: E402
from arbit_data.live.normalize import normalize_play  # noqa: E402
from arbit_data.live.play_facts import GameTeams, interpret, text_codes  # noqa: E402

EVENT = "401873036"
UNIFORMS = {"26": R.SEA, "3": R.CHI}  # ESPN team IDs: Seattle, Chicago
OUT = ROOT / "data/sprites/review/generated"
# The plays real_plays.py choreographs by hand, by ESPN play ID suffix.
COMPARE = {"1939": "td-pass", "1240": "pass-tackle", "410": "run", "2316": "sack", "3679": "interception"}


def roster_names() -> dict[str, str]:
    """ESPN ID to a name in the play text's style ("S.Darnold"), from the stored 2026 roster."""
    import pyarrow.parquet as pq

    inventory = json.loads((ROOT / "docs/research/nflverse-inventory-2026-10-31.json").read_text())
    entry = next(f for f in inventory["files"] if f["logical_key"].endswith("rosters/roster_2026"))
    names = {}
    for row in pq.read_table(ROOT / "data/nflverse/objects" / entry["original_sha256"]).to_pylist():
        if row.get("espn_id") and row.get("first_name") and row.get("last_name"):
            last = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", row["last_name"])
            names[str(row["espn_id"])] = f"{row['first_name'][0]}.{last}"
    return names


def scripts() -> dict[str, PlayScript]:
    plays, teams = coverage.captured(ROOT / "data/live-captures")
    normalized = [normalize_play(raw, EVENT, 2026) for raw in plays[EVENT].values()]
    context = GameTeams.build(*teams[EVENT], seen=text_codes(p.text for p in normalized))
    names = roster_names()
    made = {}
    for play in normalized:
        seed = f"{play.provider_id}:{content_hash(play.model_dump(mode='json'))}"
        script = choreograph(interpret(play, context), seed, names)
        if script is not None:
            made[play.provider_id.removeprefix(EVENT)] = script
    return made


def offset(pose: str, hold: str, facing_left: bool) -> tuple[float, float]:
    """Where the ball sits relative to an actor's feet, in yards, for a frame and a hold."""
    frame = P.CYCLES[pose][0][0] if pose in P.CYCLES else pose
    if hold == "chest":
        rows = P.FRAMES[frame]
        cx, cy = P.ANCHORS[frame.removesuffix("_e")]["chest"]
        dx, dy = (cx - P.torso_x(rows)) * P.ART_PIXEL_YARDS, (len(rows) - cy) * P.ART_PIXEL_YARDS
    else:
        dx, dy = P.ball_offset(frame)
    return (-dx if facing_left else dx), dy


class ScriptActor(P.Actor):
    """A renderer actor whose facing can change by segment, for a chase toward its own goal."""

    def __init__(self, *args, facings: list[str | None], **kwargs):
        super().__init__(*args, **kwargs)
        self.default_left = self.facing_left
        self.facings = facings

    def frame(self, t: float):
        index = next((i for i, seg in enumerate(self.segments) if t < seg[1]), len(self.segments) - 1)
        facing = self.facings[index]
        self.facing_left = self.default_left if facing is None else facing == "left"
        return super().frame(t)


def draw(script: PlayScript, name: str) -> None:
    actors: dict[str, P.Actor] = {}
    for spec in script.actors:
        team = script.offense if spec.side == "offense" else script.defense
        first = spec.segments[0]
        actor = ScriptActor(
            R.SKIN_SETS[int(spec.espn_id) % 2],
            first.x0,
            first.z0,
            spec.facing == "left",
            facings=[seg.facing for seg in spec.segments],
        )
        actor.uniform = UNIFORMS.get(team or "")
        actor.label = spec.label
        actor.segments = [(s.start, s.end, s.x0, s.z0, s.x1, s.z1, s.pose) for s in spec.segments]
        actor.clock, actor.x, actor.z = spec.segments[-1].end, spec.segments[-1].x1, spec.segments[-1].z1
        actors[spec.key] = actor
    for seg in script.ball:
        if seg.state == "held" and seg.actor in actors:
            actors[seg.actor].carries.append((seg.start, seg.end))

    def point(end, t: float) -> P.Point:
        if end.point is not None:
            return tuple(end.point)  # type: ignore[return-value]
        actor = actors[end.actor]
        x, z, pose = actor.where(t)
        index = next((i for i, seg in enumerate(actor.segments) if t < seg[1]), len(actor.segments) - 1)
        facing = actor.facings[index]
        left = actor.default_left if facing is None else facing == "left"
        dx, dy = offset(pose, end.hold or "hand", left)
        return (x + dx, dy, z)

    flights = {}
    for index, seg in enumerate(script.ball):
        if seg.state == "flight":
            # The catch pose is the one that ends at the catch, so read the hands just before it.
            flights[index] = P.flight(
                seg.start, seg.end, point(seg.origin, seg.start), point(seg.target, seg.end - 1e-3)
            )

    def ball(t: float):
        for index, seg in enumerate(script.ball):
            if seg.start <= t < seg.end:
                if seg.state == "rest":
                    return P.Ball(tuple(seg.at), "flat")  # type: ignore[arg-type]
                if seg.state == "flight":
                    return P.Ball(flights[index](t), seg.spin)
                return None  # held: drawn with the actor
        return None

    lines = [(line.x, P.LOS_COLOR if line.kind == "scrimmage" else P.FIRST_DOWN_COLOR) for line in script.lines]
    R.render(name, script.duration, list(actors.values()), ball, lambda _t: 50.0, lines, script.caption)
    (P.OUT / f"{name}.json").write_text(script.model_dump_json(indent=1) + "\n")


def main(args: list[str]) -> None:
    P.SHOT, P.OUT = P.WIDE, OUT
    OUT.mkdir(parents=True, exist_ok=True)
    made = scripts()
    if "--compare" in args:
        wanted = {key: f"generated-{label}" for key, label in COMPARE.items()}
    elif "--all" in args:
        wanted = {key: f"{key.zfill(4)}-{script.template}" for key, script in made.items()}
    else:
        wanted = {key: f"{key.zfill(4)}-{made[key].template}" for key in args if key in made}
    if not wanted:
        print(
            f"{len(made)} plays have scripts: "
            + ", ".join(f"{k}:{s.template}" for k, s in sorted(made.items(), key=lambda kv: int(kv[0])))
        )
        return
    for key, name in wanted.items():
        draw(made[key], name)


if __name__ == "__main__":
    main(sys.argv[1:])
