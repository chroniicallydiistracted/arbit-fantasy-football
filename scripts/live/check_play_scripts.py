"""Rule check of the play choreographer over every captured game (automation slices 2 and 3).

Reads only the private captures in data/live-captures, like `play_facts_coverage.py`: every play is
normalized, interpreted and choreographed with the current code, and each script, and each try
after a touchdown, is checked against the rules the owner set for the animation. Prints what was
made, what has no script and why, and every broken rule with one example. Makes no requests and
writes nothing.

Players line up by their 2026 depth chart positions (`positions.py`), as the app will draw them;
--no-positions checks the fallback placement used when a position is unknown.

Usage: uv run python scripts/live/check_play_scripts.py [captures dir] [--no-positions]
"""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import play_facts_coverage as coverage  # noqa: E402
import positions as depth  # noqa: E402
from arbit_data.league import content_hash  # noqa: E402
from arbit_data.live import alignment as A  # noqa: E402
from arbit_data.live import choreography as C  # noqa: E402
from arbit_data.live import kicking as K  # noqa: E402
from arbit_data.live.normalize import normalize_play  # noqa: E402
from arbit_data.live.play_facts import GameTeams, PlayFacts, interpret, text_codes  # noqa: E402

SEASON = 2026
PACED = False
# Poses a player may hold still: on the ground, kneeling, holding for a kick, on a recovered ball,
# celebrating. Anyone else standing still longer than LONGEST_STILL after the snap is frozen.
RESTING = ("ground", "rise", "kneel", "point", "arms", "spike", "hold_", "recover", "snap_", "off_")
# Where each kind of position starts at the snap, in yards past the line (OWN-036). Kick units
# and returners line up by the kick instead.
BOXES = {
    "OL": (-1.0, -0.2),  # the center stands right over the ball
    "TE": (-1.0, -0.3),
    "WR": (-8.0, 0.0),
    "RB": (-8.0, -3.0),
    "FB": (-8.0, -3.0),
    "QB": (-6.0, -0.4),
    "DL": (0.9, 1.1),
    "EDGE": (0.9, 1.1),
    "LB": (3.0, 6.0),
    "CB": (4.0, 8.0),
    "NB": (4.0, 7.0),
    "S": (6.0, 15.0),
}
KICKS = ("punt", "kickoff", "field_goal", "extra_point")
FIRST_MOVES = {"RUN", "DROP", "drive"}


class Report:
    def __init__(self) -> None:
        self.problems: Counter[str] = Counter()
        self.examples: dict[str, tuple[str, str]] = {}
        self.positioned: Counter[str] = Counter()  # drawn players with a known position, or not
        self.first_moves: Counter[tuple[str, str, str]] = Counter()

    def flag(self, kind: str, facts: PlayFacts, detail: str) -> None:
        self.problems[kind] += 1
        self.examples.setdefault(kind, (facts.text[:120], detail))


def motion(script: C.PlayScript, facts: PlayFacts, report: Report) -> None:
    """Natural motion (OWN-033) and the script's own consistency."""
    keys = [actor.key for actor in script.actors]
    if len(keys) != len(set(keys)):
        report.flag("actor key used twice", facts, str(keys))
    for actor in script.actors:
        if actor.espn_id is None and not actor.label and actor.role != "official":
            report.flag("player without an ID or a text name", facts, actor.key)
        runs = []
        for seg in actor.segments:
            seconds = seg.end - seg.start
            speed = math.hypot(seg.x1 - seg.x0, seg.z1 - seg.z0) / seconds if seconds else 0.0
            limit = (
                C.TOP_SPEED * 1.08 if seg.pose in C.CYCLES else C.MOMENTUM.get(seg.pose, C.STILL)
            )
            if speed > limit + 1e-6:
                report.flag(f"too fast: {seg.pose}", facts, f"{actor.key} {speed:.1f}")
            if seg.pose == "RUN" and seconds > 0.25:
                runs.append(speed)
            held = seg.pose not in C.CYCLES and seg.pose not in C.MOMENTUM
            if held and not seg.pose.startswith(RESTING) and seg.start > 0:
                if seconds > C.LONGEST_STILL + 1e-6:
                    report.flag(f"frozen: {seg.pose}", facts, f"{actor.key} {seconds:.2f}s")
        if runs and min(runs) < C.SLOWEST_RUN:
            report.flag("slow-motion run", facts, f"{actor.key} {min(runs):.1f}")
        if runs and max(runs) - min(runs) > 0.15:
            report.flag("pace changes", facts, actor.key)
        for before, after in zip(actor.segments, actor.segments[1:], strict=False):
            if abs(before.end - after.start) > 1e-3 or abs(before.x1 - after.x0) > 1e-3:
                report.flag("gap in a timeline", facts, actor.key)
    lines = [line.x for line in script.lines if line.kind == "scrimmage"]
    if lines and script.template not in ("kickoff",):
        # At the snap the offense is on or behind the line and the defense on or beyond it, no
        # deeper than a safety; a kick returner waits where the kick comes down (OWN-035).
        los = lines[0]
        for actor in script.actors:
            x0 = actor.segments[0].x0
            if actor.role == "returner":
                continue
            if actor.side == "offense" and x0 > los + 1e-6:
                report.flag("offense starts past the line", facts, f"{actor.key} {x0 - los:+.1f}")
            if actor.side == "defense" and not los - 1e-6 <= x0 <= los + C.DEEPEST + 1e-6:
                report.flag("defense starts off its side", facts, f"{actor.key} {x0 - los:+.1f}")
    for actor in script.actors:  # nobody runs before the snap but a player flagged for it
        early = [
            seg for seg in actor.segments if seg.pose in C.CYCLES and seg.start < C.SNAP - 1e-6
        ]
        # A ball carrier in jet motion moves along the line before the snap, as the rules allow.
        jet = actor.role == "rusher" and all(abs(s.x1 - s.x0) <= abs(s.z1 - s.z0) for s in early)
        if early and actor.role != "penalized" and not jet:
            report.flag("runs before the snap", facts, actor.key)
    if script.template == "kickoff" and lines:
        # 2026 kickoff: coverage on the receiving 40, never past it; the kicker behind the tee.
        for actor in script.actors:
            x0 = actor.segments[0].x0
            if actor.side == "offense" and x0 > lines[0] + 25 + 1e-6:
                report.flag("kickoff coverage past the receiving 40", facts, f"{x0:.1f}")
    ball = sorted(script.ball, key=lambda seg: seg.start)
    if abs(ball[0].start) > 1e-6 or abs(ball[-1].end - script.duration) > 1e-3:
        report.flag("ball missing at an end", facts, script.template)
    for before, after in zip(ball, ball[1:], strict=False):
        if abs(before.end - after.start) > 1e-3:
            report.flag(
                "ball gap", facts, f"{before.state}->{after.state} {before.end} {after.start}"
            )
    ids = [actor.espn_id for actor in script.actors if actor.espn_id]
    if len(ids) != len(set(ids)):
        report.flag("player drawn twice", facts, script.template)
    # Beyond those ESPN names, only the team's snapper and, on a run, its quarterback (OWN-037).
    named = [a.espn_id for a in script.actors if a.espn_id and a.role not in ("snapper", "quarterback")]
    if not set(named) <= {p.espn_id for p in facts.players}:
        report.flag("player ESPN doesn't name", facts, script.template)
    for prop in script.props:
        if not (-10 <= prop.at[0] <= 110 and 0 <= prop.at[2] <= C.FIELD_WIDTH):
            report.flag("flag off the field", facts, str(prop.at))


def alignment(script: C.PlayScript, facts: PlayFacts, report: Report) -> None:
    """Players start where their positions line up and clear of each other (OWN-036)."""
    lines = [line.x for line in script.lines if line.kind == "scrimmage"]
    if not lines:
        return
    los = lines[0]
    starts = []
    for actor in script.actors:
        first = actor.segments[0]
        starts.append((actor.key, first.x0, first.z0))
        if actor.espn_id:
            report.positioned["with a position" if actor.position else "without"] += 1
        kind = A.group(actor.position)
        if kind is None or script.template in KICKS or actor.role in ("returner", "blocker"):
            continue
        if (kind in A.DEFENSE) != (actor.side == "defense"):
            continue  # playing the other side, such as a safety on the punt team: no base spot
        low, high = BOXES.get(kind, (-99.0, 99.0))
        if not low - 1e-6 <= first.x0 - los <= high + 1e-6:
            report.flag(f"{kind} starts out of his box", facts, f"{actor.key} {actor.position} {first.x0 - los:+.1f}")
        moved = next((s for s in actor.segments if s.start >= C.SNAP and s.pose not in ("ready", "drop_a", "drop_b", "drop_c")), None)
        if moved is not None:
            context = "pass" if script.template in ("pass", "interception", "sack", "scramble") else script.template
            report.first_moves[(kind, context, moved.pose if moved.pose in FIRST_MOVES else "other")] += 1
    for index, (key, x, z) in enumerate(starts):
        for other, ox, oz in starts[index + 1 :]:
            if math.hypot(x - ox, z - oz) < 0.9:
                report.flag("two players start on top of each other", facts, f"{key} and {other}")


def where(actor: C.Actor, t: float) -> tuple[float, float]:
    for seg in actor.segments:
        if seg.start <= t < seg.end:
            share = (t - seg.start) / (seg.end - seg.start) if seg.end > seg.start else 1.0
            return seg.x0 + (seg.x1 - seg.x0) * share, seg.z0 + (seg.z1 - seg.z0) * share
    last = actor.segments[-1]
    return last.x1, last.z1


def realism(script: C.PlayScript, facts: PlayFacts, report: Report) -> None:
    """The owner's review of the play-type clips (OWN-037)."""
    actors = {actor.key: actor for actor in script.actors}
    receiver = actors.get("receiver")
    for flight in (s for s in script.ball if s.state == "flight" and s.target and s.target.actor == "receiver"):
        if receiver is None:
            continue
        catching = next((s for s in receiver.segments if s.start <= flight.end - 1e-3 < s.end), None)
        if catching is None or not catching.pose.startswith("catch") or abs(catching.end - flight.end) > 1e-3:
            report.flag("ball and receiver don't arrive together", facts, catching.pose if catching else "")
        waiting = [
            s.pose for s in receiver.segments
            if flight.end - 0.6 < s.end <= flight.end and s.pose not in C.CYCLES and not s.pose.startswith("catch")
        ]
        if waiting:
            report.flag("receiver waits for the ball", facts, str(waiting))
        passer = actors.get("passer")
        if passer is not None:
            thrown, caught = where(passer, flight.start), where(receiver, flight.end - 1e-3)
            speed = math.hypot(caught[0] - thrown[0], caught[1] - thrown[1]) / max(0.05, flight.end - flight.start - 0.25)
            if speed > C.BULLET + 1.5:
                report.flag("pass faster than a bullet", facts, f"{speed:.1f}")
        catch_point = where(receiver, flight.end - 1e-3)
        for actor in script.actors:
            if actor.side != "defense":
                continue
            # Waiting at the catch spot before the ball gets there, as in the first review.
            early = [
                s for s in actor.segments
                if flight.end - 1.0 < s.end and s.start < flight.end - 0.3
                and s.pose not in C.CYCLES and s.pose not in C.MOMENTUM
                and math.hypot(s.x0 - catch_point[0], s.z0 - catch_point[1]) < 1.0
            ]
            if early:
                report.flag("defender waits at the catch spot", facts, f"{actor.key} {early[0].pose}")
    lines = [line.x for line in script.lines if line.kind == "scrimmage"]
    snapper = actors.get("snapper")
    if snapper is not None and lines and script.template not in ("punt", "field_goal", "extra_point", "two_point"):
        if any(abs(s.x0 - lines[0]) > 0.5 or abs(s.x1 - lines[0]) > 0.5 for s in snapper.segments):
            report.flag("snapper leaves the ball", facts, "")
    quarterback = actors.get("quarterback")
    if quarterback is not None and script.template == "run":
        held = [s for s in script.ball if s.state == "held" and s.actor == "quarterback"]
        if not held or held[0].end > C.SNAP + 0.9:
            report.flag("handoff not right after the snap", facts, f"{held[0].end if held else None}")
        if not any(s.state == "held" and s.actor == "rusher" and s.start >= held[0].end for s in script.ball):
            report.flag("ball not handed to the back", facts, "")
    passer = actors.get("passer")
    if script.template == "sack" and passer is not None:
        hit = next((s for s in passer.segments if s.pose == "hit_back"), None)
        before = [s for s in passer.segments if hit and s.end > hit.start - 0.5 and s.start < hit.start]
        if hit is not None and not any(s.pose == "RUN" for s in before):
            report.flag("sacked quarterback doesn't escape", facts, "")
    for actor in script.actors:
        lunge = next((s for s in actor.segments if s.pose == "lunge" and actor.role in ("tackler", "assistedBy")), None)
        if lunge is None:
            continue
        aim = (lunge.x1, lunge.z1)
        # The first review's fault: he stops at the tackle spot, backs off, then comes again.
        stopped = [
            s for s in actor.segments
            if max(C.SNAP, lunge.start - 3.0) < s.start < lunge.start - 0.5 and s.pose not in C.CYCLES
            and s.pose not in C.MOMENTUM and math.hypot(s.x0 - aim[0], s.z0 - aim[1]) < 1.5
        ]
        if stopped:
            later = [
                where(actor, t) for t in
                [stopped[0].end + 0.1 * k for k in range(60) if stopped[0].end + 0.1 * k < lunge.start]
            ]
            if any(math.hypot(x - aim[0], z - aim[1]) > 2.0 for x, z in later):
                report.flag("tackler backs off and comes again", facts, actor.key)


def crossing(script: C.PlayScript) -> tuple[float, float, float] | None:
    """Where a place kick reaches the end line, if it does."""
    return next(
        (
            seg.target.point
            for seg in script.ball
            if seg.state == "flight"
            and seg.target
            and seg.target.point
            and abs(seg.target.point[0] - K.END_LINE) < 1e-6
        ),
        None,
    )


def between_the_posts(point: tuple[float, float, float] | None) -> bool:
    return point is not None and abs(point[2] - K.POST_Z) < K.POST_HALF and point[1] > K.CROSSBAR


def outcome(script: C.PlayScript, facts: PlayFacts, report: Report) -> None:
    """The script shows what ESPN says happened."""
    kick, held = facts.kick, [seg for seg in script.ball if seg.state == "held"]
    if script.template in ("punt", "kickoff") and kick and kick.landing is not None:
        if kick.result in (
            "returned",
            "fair_catch",
            "out_of_bounds",
            "downed",
            "short_of_landing_zone",
            "muffed",
        ):
            flights = [seg for seg in script.ball if seg.state == "flight" and seg.start > 1.0]
            first = flights[0] if flights else None
            point = first.target.point if first and first.target else None
            landed = (
                point[0]
                if point
                else next(
                    (
                        a.segments[0].x0
                        for a in script.actors
                        if first and first.target and a.key == first.target.actor
                    ),
                    None,
                )
            )
            if landed is not None and first and first.target and first.target.actor:
                returner = next(a for a in script.actors if a.key == first.target.actor)
                landed = next(
                    s for s in returner.segments if s.start <= first.end - 1e-3 < s.end
                ).x1
            if landed is None or abs(landed - kick.landing) > 1.6:
                report.flag("kick comes down off its spot", facts, f"{landed} vs {kick.landing}")
    if script.template == "field_goal" and kick:
        cross = crossing(script)
        if kick.result == "good" and not between_the_posts(cross):
            report.flag("good kick not through the posts", facts, str(cross))
        if kick.miss == "wide_left" and not (cross and cross[2] < K.POST_Z - K.POST_HALF):
            report.flag("wide left not on the near side", facts, str(cross))
        if kick.miss == "wide_right" and not (cross and cross[2] > K.POST_Z + K.POST_HALF):
            report.flag("wide right not on the far side", facts, str(cross))
    if script.template in ("punt", "kickoff") and kick and kick.result == "returned" and held:
        carrier = next(a for a in script.actors if a.key == held[-1].actor)
        end = carrier.segments[-1].x1
        if facts.touchdown:
            if end > 0:
                report.flag("return touchdown short of the goal", facts, str(end))
        elif abs(end - facts.action_end) > 0.05:  # type: ignore[operator]
            report.flag("return off ESPN's spot", facts, f"{end} vs {facts.action_end}")
    if script.template == "fumble":
        recoverer = next((p.espn_id for p in facts.players if p.role == "recoverer"), None)
        holder = next((a for a in script.actors if a.espn_id == recoverer), None)
        if recoverer and (holder is None or not held or held[-1].actor != holder.key):
            report.flag("fumble never reaches the recoverer", facts, str(recoverer))
        elif recoverer and holder:
            got = held[-1].start
            at = next(
                (s for s in holder.segments if s.start <= got + 1e-6 < s.end), holder.segments[-1]
            )
            # Where the ball was just before he got it: lying loose, or the end of its last bounce.
            loose = [s for s in script.ball if s.state in ("rest", "flight") and s.end <= got + 1e-6 and s.start > C.SNAP]
            rest = [
                s if s.state == "rest" else s.model_copy(update={"at": s.target.point})
                for s in loose[-1:]
                if s.state == "rest" or (s.target is not None and s.target.point is not None)
            ]
            if rest and math.hypot(rest[-1].at[0] - at.x0, rest[-1].at[2] - at.z0) > 2.2:  # type: ignore[index]
                report.flag(
                    "recoverer takes the ball from afar", facts, f"{rest[-1].at} vs {at.x0},{at.z0}"
                )
            if rest and abs(rest[-1].at[0] - facts.fumble.spot) > 0.05:  # type: ignore[index, union-attr, operator]
                report.flag("ball recovered off ESPN's spot", facts, str(rest[-1].at))
    if script.template == "penalty" and not script.props:
        report.flag("penalty without a flag", facts, "")
    if facts.penalties and not script.props:
        report.flag("penalty without a flag", facts, script.template)


def espn_games(root: Path):
    """Each captured game's plays as ESPN gave them."""
    plays, teams = coverage.captured(root)
    for event, items in plays.items():
        normalized = [normalize_play(raw, event, SEASON) for raw in items.values()]
        yield event, normalized, teams[event]


def nfl_games(root: Path, details: Path):
    """Each game in an NFL API weekly game details response, as the NFL lane stores it (OWN-041):
    joined to ESPN's event through nflverse's schedule, players through its players table."""
    import json

    from arbit_data.live.nfl_api import GameLink, to_live_plays

    _plays, teams = coverage.captured(root)
    ids = {r["gsis_id"]: str(r["espn_id"]) for r in depth._table("players/players") if r.get("gsis_id") and r.get("espn_id")}
    events = {str(g["old_game_id"]): str(g["espn"]) for g in depth._table("schedules/games") if g.get("espn")}
    for game in json.loads(details.read_text()):
        elias = next(x["id"] for x in game["externalIds"] if x["source"] == "elias")
        event = events.get(elias)
        if event not in teams:
            continue
        home, away, home_code, away_code = teams[event]
        link = GameLink(game["id"], event, home, away, home_code, away_code)
        yield event, list(to_live_plays(game, link, ids, SEASON)), teams[event]


def main(root: Path, use_positions: bool = True, details: Path | None = None) -> None:
    made, none, report, paced = Counter(), Counter(), Report(), Counter()
    positions = depth.load() if use_positions else {}
    units = depth.units() if use_positions else {}
    football = 0
    games = nfl_games(root, details) if details else espn_games(root)
    for event, normalized, game_teams in games:
        normalized.sort(key=lambda p: int(p.sequence or 0))
        context = GameTeams.build(*game_teams, seen=text_codes(p.text for p in normalized))
        game = depth.GameUnits(units, game_teams)
        for play in normalized:
            facts = interpret(play, context)
            if facts.shape in ("timeout", "other"):
                continue
            football += 1
            seed = f"{play.provider_id}:{content_hash(play.model_dump(mode='json'))}"
            now = game.now()
            game.saw(facts)
            script = C.choreograph(facts, seed, positions=positions, units=now)
            if PACED and script is not None and play.snap_at and play.whistle_at:
                from datetime import datetime

                from arbit_data.live.pacing import pace

                real = (datetime.fromisoformat(play.whistle_at.replace("Z", "+00:00")) - datetime.fromisoformat(play.snap_at.replace("Z", "+00:00"))).total_seconds()
                script = pace(script, real)
                paced["plays"] += 1
                paced["at real time" if abs(script.whistle - C.SNAP - real) < 0.05 else "kept Arbit's timing"] += 1
            if script is None:
                none[f"{facts.shape} ({facts.reason or facts.template or 'no template'})"] += 1
            else:
                made[script.template] += 1
                motion(script, facts, report)
                outcome(script, facts, report)
                alignment(script, facts, report)
                realism(script, facts, report)
            if facts.point_after and facts.touchdown:
                tried = K.choreograph_try(facts, seed, positions=positions, units=now)
                if tried is None:
                    none[f"try ({facts.point_after.kind})"] += 1
                    continue
                made[f"try: {tried.template}"] += 1
                motion(tried, facts, report)
                cross = crossing(tried)
                if (
                    tried.template == "extra_point"
                    and facts.point_after.good
                    and not between_the_posts(cross)
                ):
                    report.flag("good extra point not through the posts", facts, str(cross))
                if facts.point_after.miss == "wide_left" and not (
                    cross and cross[2] < K.POST_Z - K.POST_HALF
                ):
                    report.flag("extra point wide left not on the near side", facts, str(cross))
    print(f"Football plays: {football}. Scripts: {sum(made.values())}.\n")
    if PACED:
        print(f"Paced to the NFL's snap-to-whistle times (OWN-041): {dict(paced)}\n")
    print("| Script | Count |\n| --- | ---: |")
    for name, count in made.most_common():
        print(f"| {name} | {count} |")
    print("\n| No script | Count |\n| --- | ---: |")
    for name, count in none.most_common():
        print(f"| {name} | {count} |")
    print(f"\nDrawn players with a depth chart position: {dict(report.positioned)}")
    print("\n| Position | Play | First move after the snap | Count |\n| --- | --- | --- | ---: |")
    for (kind, context, pose), count in sorted(report.first_moves.items()):
        print(f"| {kind} | {context} | {pose} | {count} |")
    print(f"\nBroken rules: {sum(report.problems.values())}")
    for kind, count in report.problems.most_common():
        text, detail = report.examples[kind]
        print(f"- {kind}: {count}, such as {detail!r} in {text!r}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # --nfl=PATH: the plays of an NFL API weekly game details response, as the NFL lane stores them.
    nfl = next((Path(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--nfl=")), None)
    PACED = "--paced" in sys.argv  # pace each NFL play to its real snap-to-whistle time
    main(Path(args[0]) if args else Path("data/live-captures"), "--no-positions" not in sys.argv, nfl)
