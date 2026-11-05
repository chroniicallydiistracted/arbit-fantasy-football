"""Audit of the play scripts against the review renderer, over every captured game (OWN-036).

`check_play_scripts.py` checks the football rules. This checks what the renderer needs to draw
each script: every pose has a sprite frame, a carried ball has a hand or chest to sit on in every
frame it's carried, every flight starts and ends at a player who is in the play or at a point,
every player ESPN names has a name tag, and every caption fits its bar. Every stadium board
(slice 5) has a glyph for each character it shows, and each text fits its space. Players line up by
their depth chart positions and carry roster names, as in the review renders. Reads only private
data in data/; writes nothing.

Usage: uv run --with pillow --with numpy --with pyarrow python scripts/sprites/audit_render.py
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import board as B  # noqa: E402
import check_boards  # noqa: E402
import play_facts_coverage as coverage  # noqa: E402
import positions as depth  # noqa: E402
import preview as P  # noqa: E402
from arbit_data.league import content_hash  # noqa: E402
from arbit_data.live.board import GameBoard, PlayBoard  # noqa: E402
from arbit_data.live.choreography import PlayScript, choreograph  # noqa: E402
from arbit_data.live.kicking import choreograph_try  # noqa: E402
from arbit_data.live.normalize import normalize_play  # noqa: E402
from arbit_data.live.play_facts import GameTeams, interpret, text_codes  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from render_script import roster_names  # noqa: E402

CAPTION_ROOM = P.WIDE.width - 16 - 16 - 20  # beside the note on the right, with a gap
NOTE = "Re-creation from play-by-play"


def frames(pose: str) -> list[str]:
    return list(P.CYCLES[pose][0]) if pose in P.CYCLES else [pose.removesuffix("_e")]


def audit(script: PlayScript, text: str, found: Counter, examples: dict, measure) -> None:
    def flag(kind: str, detail: str) -> None:
        found[kind] += 1
        examples.setdefault(kind, (text[:110], detail))

    keys = {actor.key for actor in script.actors}
    for actor in script.actors:
        for seg in actor.segments:
            if any(name not in P.FRAMES for name in frames(seg.pose)):
                flag("pose without a sprite frame", f"{actor.key} {seg.pose}")
        if actor.espn_id and not actor.label:
            flag("named player without a name tag", f"{actor.key} {actor.espn_id}")
        if actor.label and len(actor.label) > 24:
            flag("name tag too long", actor.label)
    for seg in script.ball:
        if seg.state == "held":
            if seg.actor not in keys:
                flag("ball held by nobody in the play", str(seg.actor))
                continue
            holder = next(a for a in script.actors if a.key == seg.actor)
            for part in holder.segments:
                if part.end > seg.start and part.start < seg.end:
                    missing = [n for n in frames(part.pose) if n not in P.ANCHORS]
                    if missing:
                        flag("carried ball with nowhere to sit", f"{holder.key} {part.pose}")
        if seg.state == "flight":
            for end in (seg.origin, seg.target):
                if end is None or (end.actor is None) == (end.point is None):
                    flag("flight end not a player or a point", str(end))
                elif end.actor is not None and end.actor not in keys:
                    flag("flight to or from nobody in the play", end.actor)
    if script.duration > 30:
        flag("clip longer than 30 seconds", f"{script.duration:.1f}")
    if measure(script.caption) > CAPTION_ROOM - measure(NOTE, True):
        flag("caption runs into the note", script.caption)


def audit_board(board: PlayBoard, text: str, found: Counter, examples: dict) -> None:
    def flag(kind: str, detail: str) -> None:
        found[kind] += 1
        examples.setdefault(kind, (text[:110], detail))

    for state in (board.before, board.after):
        for cell, (shown, room) in B.texts(state).items():
            if B.missing(shown):
                flag("board character without a glyph", f"{cell} {shown!r}")
            elif B.text_width(shown) > room:
                flag("board text too wide for its space", f"{cell} {shown!r}")
        for side in (state.away, state.home):
            if side.score is not None and B.text_width(str(side.score), 2) > B.COLUMN:
                flag("board score too wide", str(side.score))
        if state.clock and (B.missing(state.clock) or B.text_width(state.clock, 2) > B.MIDDLE):
            flag("board clock without a glyph or too wide", state.clock)
    for result in board.results:
        under = B.team_line(result, result.team_id and "MMM")  # the widest a team code can be
        if B.missing(result.text) or B.missing(under):
            flag("board result without a glyph", f"{result.text} {under}")
        elif B.lines(result.text) is None:
            flag("board result too wide for two large lines", result.text)
        elif B.text_width(under) > B.WIDTH - 8:
            flag("board result's team line too wide", under)
    for side in (board.before.away, board.before.home):
        if not B.logo(side.code):
            flag("team without a logo", side.code)


def main() -> None:
    plays, teams = coverage.captured(ROOT / "data/live-captures")
    names, positions, units = roster_names(), depth.load(), depth.units()
    big = ImageFont.load_default(size=P.WIDE.caption_size)
    small = ImageFont.load_default(size=P.WIDE.tag_size)
    canvas = ImageDraw.Draw(Image.new("RGB", (4, 4)))

    def width(text: str, tag: bool = False) -> float:
        return canvas.textlength(text, font=small if tag else big)

    found: Counter = Counter()
    examples: dict = {}
    scripts = boards = 0
    newest = check_boards.snapshots()[1]
    weeks = depth.game_weeks()
    for event, items in plays.items():
        normalized = [normalize_play(raw, event, 2026) for raw in items.values()]
        normalized.sort(key=lambda p: int(p.sequence or 0))
        context = GameTeams.build(*teams[event], seen=text_codes(p.text for p in normalized))
        game = depth.GameUnits(units, teams[event])
        competitors = newest[event]["competitions"][0]["competitors"]
        board = GameBoard(
            context,
            teams[event][2],
            teams[event][3],
            {c["team"]["id"]: [c["team"]["location"], c["team"]["displayName"]] for c in competitors},
            depth.week_rosters(weeks[event], {teams[event][0]: teams[event][2], teams[event][1]: teams[event][3]}),
        )
        for play in normalized:
            facts = interpret(play, context)
            for part in board.boards(play, facts):
                boards += 1
                audit_board(part, play.text, found, examples)
            seed = f"{play.provider_id}:{content_hash(play.model_dump(mode='json'))}"
            now = game.now()
            game.saw(facts)
            made = [choreograph(facts, seed, names, positions, now)]
            if facts.point_after and facts.touchdown:
                made.append(choreograph_try(facts, seed, names, positions, now))
            for script in made:
                if script is not None:
                    scripts += 1
                    audit(script, play.text, found, examples, width)
    print(f"Scripts audited: {scripts}. Boards audited: {boards}. Problems: {sum(found.values())}")
    for kind, count in found.most_common():
        text, detail = examples[kind]
        print(f"- {kind}: {count}, such as {detail!r} in {text!r}")


if __name__ == "__main__":
    main()
