"""Render generated play scripts with the review renderer (automation slices 2 and 3 evidence).

Builds CHI at SEA (2026-11-02, event 401873036) from the private captures: each play is normalized,
interpreted (`play_facts`), choreographed (`choreography`, with kicks, fumbles and penalties from
`kicking` and `incidents`) and drawn in the full-field view with the uniforms and field Gridiron
lists for that game, the same as `real_plays.py`. The try after each touchdown is its own clip,
named with "try". Flags are drawn thrown in from the near sideline and lying where they land.
Scripts are written next to the GIFs as JSON. Output stays in ignored data/ because it uses
Gridiron art (OWN-015).

Usage:
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py [play ID suffix ...]
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py --compare
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py --all
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/render_script.py --slice3

With no plays it lists what can be rendered. --compare renders the five plays that real_plays.py
re-creates by hand, so the two can be watched side by side. --slice3 renders the game's kicks,
tries, fumbles and penalties. A try is selected as its touchdown's suffix with "+try".
--position-tags adds each player's depth chart position to his name tag ("J.Jackson RG").
--types renders one play of each type, with position tags, into data/sprites/review/play-types.
--board renders the same plays with name tags only into data/sprites/review/board, to review the
stadium board (slice 5). Every clip has the board, built from the game's plays in order.
Players line up by those positions, as of the depth charts before the game (OWN-036). Name tags come from the stored 2026
nflverse roster by ESPN ID; a player missing from it is named from the text only when that is
unambiguous.
"""

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import board as B  # noqa: E402
import check_boards  # noqa: E402
import play_facts_coverage as coverage  # noqa: E402
import positions as depth  # noqa: E402
import preview as P  # noqa: E402
import real_plays as R  # noqa: E402  (loads the game's field and measured uniforms)
from arbit_data.league import content_hash  # noqa: E402
from arbit_data.live.board import GameBoard, PlayBoard  # noqa: E402
from arbit_data.live.choreography import PlayScript, choreograph  # noqa: E402
from arbit_data.live.kicking import choreograph_try  # noqa: E402
from arbit_data.live.normalize import normalize_play  # noqa: E402
from arbit_data.live.play_facts import GameTeams, interpret, text_codes  # noqa: E402

EVENT = "401873036"
KICKOFF = "2026-11-03T01:15Z"  # depth charts as they stood before the game (OWN-036)
UNIFORMS = {"26": R.SEA, "3": R.CHI}  # ESPN team IDs: Seattle, Chicago
CODES = {"26": "SEA", "3": "CHI"}
OUT = ROOT / "data/sprites/review/generated"
SLICE3 = ("punt", "kickoff", "field_goal", "extra_point", "two_point", "fumble", "penalty", "spike")
FLAG_YELLOW = (255, 214, 10, 255)
# One play of each type for the owner to compare with the game's video (OWN-036), by ESPN play
# ID suffix, rendered with position tags into data/sprites/review/play-types by --types.
TYPES = (
    ("pass-complete", "1240"),
    ("pass-incomplete", "85"),
    ("interception", "3679"),
    ("sack", "2316"),
    ("run", "410"),
    ("scramble", "4083"),
    ("kneel", "4297"),
    ("punt", "799"),
    ("kickoff", "40"),
    ("field-goal", "1407"),
    ("extra-point", "1939+try"),
    ("two-point-try", "3231+try"),
    ("fumble", "3095"),
    ("penalty-before-the-snap", "2028"),
    ("play-wiped-out-by-a-flag", "1794"),
    ("flag-on-a-play-that-counts", "607"),
    # OWN-037: the fouls around pass interference, all in this game.
    ("offensive-pass-interference", "2895"),
    ("holding-wipes-out-a-sack", "2785"),
    ("illegal-contact-declined", "3977"),
)
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
    # The depth charts name some players the roster has without an ESPN ID, such as Jonah Jackson.
    charts = next(f for f in inventory["files"] if f["logical_key"].endswith("depth_charts_2026"))
    table = pq.read_table(ROOT / "data/nflverse/objects" / charts["original_sha256"], columns=["espn_id", "player_name"])
    for row in table.to_pylist():
        full = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", row.get("player_name") or "")
        if row.get("espn_id") and str(row["espn_id"]) not in names and " " in full:
            first, last = full.split(" ", 1)
            names[str(row["espn_id"])] = f"{first[0]}.{last}"
    return names


def scripts() -> dict[str, PlayScript]:
    plays, teams = coverage.captured(ROOT / "data/live-captures")
    normalized = [normalize_play(raw, EVENT, 2026) for raw in plays[EVENT].values()]
    normalized.sort(key=lambda p: int(p.sequence or 0))
    context = GameTeams.build(*teams[EVENT], seen=text_codes(p.text for p in normalized))
    names = roster_names()
    positions = depth.load(before=KICKOFF)
    game = depth.GameUnits(depth.units(before=KICKOFF), teams[EVENT])  # OWN-037
    competitors = check_boards.snapshots()[1][EVENT]["competitions"][0]["competitors"]
    names = {c["team"]["id"]: [c["team"]["location"], c["team"]["displayName"]] for c in competitors}
    home, away, home_code, away_code = teams[EVENT]
    roster = depth.week_rosters(depth.game_weeks()[EVENT], {home: home_code, away: away_code})  # OWN-039
    board = GameBoard(context, home_code, away_code, names, roster)  # slice 5
    made = {}
    for play in normalized:
        seed = f"{play.provider_id}:{content_hash(play.model_dump(mode='json'))}"
        facts = interpret(play, context)
        key = play.provider_id.removeprefix(EVENT)
        units = game.now()
        game.saw(facts)
        for part in board.boards(play, facts):
            BOARDS[key if part.part == "play" else f"{key}+try"] = part
        script = choreograph(facts, seed, names, positions, units)
        if script is not None:
            made[key] = script
        tried = choreograph_try(facts, seed, names, positions, units) if facts.point_after else None
        if tried is not None:
            made[f"{key}+try"] = tried
    return made


def clip_name(key: str, script: PlayScript) -> str:
    play, _, tried = key.partition("+")
    return f"{play.zfill(4)}-{'try-' if tried else ''}{script.template}"


def flags(script: PlayScript):
    """Draw each flag: in the air on its arc from the official's hand, then lying on the turf.
    The renderer calls this once a frame, in order, so the frame count gives the time."""
    frame = [0]

    def overlay(draw, camera) -> None:
        t = frame[0] / P.FPS
        frame[0] += 1
        for prop in script.props:
            if t < prop.start:
                continue
            if t < prop.land:
                share = (t - prop.start) / (prop.land - prop.start)
                x = prop.origin[0] + (prop.at[0] - prop.origin[0]) * share
                z = prop.origin[2] + (prop.at[2] - prop.origin[2]) * share
                y = prop.origin[1] * (1 - share) + 2.5 * math.sin(math.pi * share)
            else:
                x, y, z = prop.at
            sx, sy, per_yard = camera.project(x, y, z)
            half = max(3.0, per_yard * 0.32)
            if t < prop.land:  # tumbling in the air: a small square that turns
                turn = 4 * math.pi * (t - prop.start)
                corners = [(sx + half * math.cos(turn + k * math.pi / 2), sy + half * math.sin(turn + k * math.pi / 2)) for k in range(4)]
                draw.polygon(corners, fill=FLAG_YELLOW, outline=(120, 90, 0, 255))
            else:  # on the turf, foreshortened
                draw.ellipse((sx - half * 1.3, sy - half * 0.45, sx + half * 1.3, sy + half * 0.45), fill=FLAG_YELLOW, outline=(120, 90, 0, 255))

    return overlay


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


TAG_POSITIONS = False  # --position-tags: "J.Jackson RG", to check each player's role


def tag_colors() -> dict[str, tuple[tuple[int, int, int, int], tuple[int, int, int, int]]]:
    """Each team's name tag colors in the owner's style C (OWN-037): its most readable color that
    isn't black-like fills the name, and its second color shadows it."""
    import name_tag_preview as N

    found = {}
    for team, code in CODES.items():
        fill, second, _ = N.pair(depth.team_colors()[code])
        found[team] = ((*fill, 255), (*second, 255))
    return found


TAGS: dict = {}
BOARDS: dict[str, PlayBoard] = {}  # by play key, as `scripts` names them


def team_color(team: str) -> tuple[int, int, int]:
    """A team's color on the board: its name tag fill, so the two match (slice 5)."""
    return tuple(TAGS[team][0][:3]) if team in TAGS else B.WHITE  # type: ignore[return-value]


def draw(script: PlayScript, name: str, board: PlayBoard | None = None) -> None:
    actors: dict[str, P.Actor] = {}
    for spec in script.actors:
        team = (
            script.offense if spec.side == "offense" else script.defense if spec.side == "defense" else None
        )
        first = spec.segments[0]
        # A player named only in the text, such as a long snapper, gets a skin from his name.
        identity = int(spec.espn_id) if spec.espn_id else sum(map(ord, spec.label or spec.key))
        actor = ScriptActor(
            R.SKIN_SETS[identity % 2],
            first.x0,
            first.z0,
            spec.facing == "left",
            facings=[seg.facing for seg in spec.segments],
        )
        actor.uniform = UNIFORMS.get(team or "")
        actor.label = spec.label
        actor.tag_colors = TAGS.get(team or "")
        actor.official = spec.side == "official"  # stripes, never team colors (OWN-037)
        if actor.official:
            actor.uniform, actor.tag_colors = None, None
        if TAG_POSITIONS and spec.position:
            actor.label = f"{spec.label or ''} {spec.position}".strip()
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
                if seg.state == "rest":  # on the turf, or standing on a tee or for the hold
                    return P.Ball(tuple(seg.at), "upright" if seg.spin == "upright" else "flat")  # type: ignore[arg-type]
                if seg.state == "flight":
                    return P.Ball(flights[index](t), seg.spin, since=seg.start)
                return None  # held: drawn with the actor
        return None

    lines = [(line.x, P.LOS_COLOR if line.kind == "scrimmage" else P.FIRST_DOWN_COLOR) for line in script.lines]
    shown = B.Board(board, script.whistle, team_color) if board is not None else None
    seconds = max(script.duration, shown.length) if shown is not None else script.duration
    R.render(name, seconds, list(actors.values()), ball, lambda _t: 50.0, lines, script.caption, overlay=flags(script), backdrop=shown)
    (P.OUT / f"{name}.json").write_text(script.model_dump_json(indent=1) + "\n")


def main(args: list[str]) -> None:
    global TAG_POSITIONS, TAGS
    TAG_POSITIONS = "--position-tags" in args
    TAGS = tag_colors()
    args = [a for a in args if a != "--position-tags"]
    P.SHOT, P.OUT = P.WIDE, OUT
    if "--types" in args:
        TAG_POSITIONS, P.OUT = True, OUT.parent / "play-types-2"  # the second comparison (OWN-037)
    if "--board" in args:
        P.OUT = OUT.parent / "board"  # slice 5
        args = [*args, "--types"]
    P.OUT.mkdir(parents=True, exist_ok=True)
    made = scripts()
    if "--types" in args:
        wanted = {key: f"{index:02d}-{label}-{key.replace('+', '-')}" for index, (label, key) in enumerate(TYPES, 1)}
    elif "--compare" in args:
        wanted = {key: f"generated-{label}" for key, label in COMPARE.items()}
    elif "--all" in args:
        wanted = {key: clip_name(key, script) for key, script in made.items()}
    elif "--slice3" in args:
        wanted = {key: clip_name(key, script) for key, script in made.items() if script.template in SLICE3}
    else:
        wanted = {key: clip_name(key, made[key]) for key in args if key in made}
    if not wanted:
        print(
            f"{len(made)} plays have scripts: "
            + ", ".join(f"{k}:{s.template}" for k, s in sorted(made.items(), key=lambda kv: (int(kv[0].partition("+")[0]), kv[0])))
        )
        return
    for key, name in wanted.items():
        draw(made[key], name, BOARDS.get(key))


if __name__ == "__main__":
    main(sys.argv[1:])
