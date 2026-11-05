"""The real ESPN plays in tests/fixtures/live, interpreted and choreographed, for the play tests."""

import json
import re
from pathlib import Path

from arbit_data.live.choreography import PlayScript, choreograph
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, PlayFacts, interpret

ROOT = Path(__file__).parents[3]
CASES = {
    case["name"]: case
    for case in json.loads((ROOT / "tests/fixtures/live/play-facts.examples.json").read_text())[
        "cases"
    ]
}
FRAMES = {
    match.group(1)
    for path in [
        *(ROOT / "assets/sprites/frames").glob("*.txt"),
        *(ROOT / "assets/sprites/officials").glob("*.txt"),  # the officials' frames (OWN-037)
    ]
    for match in re.finditer(r"^== (\S+)", path.read_text(), re.M)
}
# The fixture players' 2026 depth chart positions, by ESPN ID, best first (OWN-036).
POSITIONS = {
    espn_id: tuple(codes)
    for espn_id, codes in json.loads(
        (ROOT / "tests/fixtures/live/play-positions.example.json").read_text()
    )["positions"].items()
}
# Each team's center, long snapper and quarterback, by nflverse abbreviation (OWN-037).
TEAMS = json.loads((ROOT / "tests/fixtures/live/team-units.example.json").read_text())
ESPN_TO_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}


def units(name: str) -> dict[str, dict[str, tuple[str, str]]]:
    """The case's two teams' units, by ESPN team ID, as the choreographer takes them."""
    case = CASES[name]
    return {
        team: {
            job: tuple(found)  # type: ignore[misc]
            for job, found in TEAMS["units"].get(ESPN_TO_NFLVERSE.get(code, code), {}).items()
        }
        for team, code in ((case["home"], case["home_code"]), (case["away"], case["away_code"]))
    }


# Every case gets a script except a lateral (left as text) and a timeout (not a play).
UNSCRIPTED = ("lateral", "timeout")
SCRIPTED = tuple(name for name in CASES if name not in UNSCRIPTED)


def facts(name: str) -> PlayFacts:
    case = CASES[name]
    play = normalize_play(case["play"], case["event_id"], 2026)
    teams = GameTeams.build(
        case["home"], case["away"], case["home_code"], case["away_code"], case["text_codes"]
    )
    return interpret(play, teams)


def script(
    name: str,
    seed: str = "test",
    names: dict[str, str] | None = None,
    positions: dict[str, tuple[str, ...]] | None = None,
    with_units: bool = False,
) -> PlayScript | None:
    return choreograph(
        facts(name), f"{name}:{seed}", names, positions, units(name) if with_units else None
    )


def at(segments, t: float):
    return next((s for s in segments if s.start <= t < s.end), segments[-1])
