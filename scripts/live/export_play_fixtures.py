"""Write tests/fixtures/live/play-facts.examples.json from the private captures.

Each case is one real ESPN core API play, chosen by game and the start of its text, trimmed to the
factual play fields the normalizer reads, with its game's teams and text codes. Embedded
references stay as data and are never fetched. Rerun after changing the case list.

Usage: uv run python scripts/live/export_play_fixtures.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import play_facts_coverage as coverage  # noqa: E402

POSITIONS = Path("tests/fixtures/live/play-positions.example.json")
TEAMS = Path("tests/fixtures/live/team-units.example.json")
OUT = Path("tests/fixtures/live/play-facts.examples.json")
KEEP = (
    "$ref",
    "id",
    "sequenceNumber",
    "type",
    "text",
    "period",
    "clock",
    "homeScore",
    "awayScore",
    "scoringPlay",
    "scoreValue",
    "modified",
    "statYardage",
    "yardsAfterCatch",
    "penalty",
    "review",
    "isTurnover",
    "isPenalty",
    "pointAfterAttempt",
)
SPOT = ("down", "distance", "yardLine", "yardsToEndzone", "team")
# (name, ESPN event, start of the play's text)
CASES = [
    ("pass_catch_spot_and_missed_pat", "401873036", "(Shotgun) S.Darnold pass deep left to J.Smith-Njigba for 43"),
    (
        "pass_without_yards_after_catch",
        "401873033",
        "(Shotgun) B.Nix pass short right to J.Coleman pushed ob at DEN 27",
    ),
    (
        "pass_incomplete_qb_hit",
        "401873023",
        "(Shotgun) B.Young pass incomplete short right to D.Waller (T.Hopper) [T.Hopper]",
    ),
    ("interception_return", "401873036", "(Shotgun) S.Darnold pass short middle intended for A.Barner INTERCEPTED"),
    ("sack", "401873036", "(Shotgun) S.Darnold sacked at SEA 19"),
    ("run_gap", "401873036", "R.Johnson right tackle to SEA 31 for 9 yards"),
    ("scramble", "401873029", "(Shotgun) G.Smith scrambles right end ran ob at LV 13"),
    ("kneel", "401873036", "C.Williams kneels to CHI 18"),
    ("home_punt_downed", "401873036", "M.Dickson punts 59 yards to CHI 4"),
    ("away_punt_returned", "401873036", "T.Taylor punts 45 yards to SEA 43"),
    ("punt_fair_catch", "401873035", "T.Way punts 54 yards to PHI 27"),
    ("punt_touchback_with_penalty", "401873035", "B.Mann punts 56 yards to end zone"),
    ("kickoff_returned", "401873036", "C.Santos kicks 56 yards from CHI 35 to SEA 9"),
    ("kickoff_touchback", "401873036", "C.Santos kicks 65 yards from CHI 35 to landing zone to end zone"),
    ("kickoff_short_of_landing_zone", "401873032", "J.Karty kicks 44 yards from LA 35 to LAC 21"),
    ("kickoff_out_of_bounds", "401873026", "T.Loop kicks 62 yards from BLT 35 to BUF 3"),
    ("kickoff_onside", "401873024", "C.Ryland kicks onside 9 yards from ARZ 35"),
    ("field_goal_good", "401873036", "C.Santos 44 yard field goal is GOOD"),
    ("field_goal_wide_right", "401873030", "W.Reichard 57 yard field goal is No Good, Wide Right"),
    ("field_goal_blocked", "401873036", "J.Myers 33 yard field goal is BLOCKED"),
    ("rams_home_spot", "401873032", "M.Stafford pass short right to P.Nacua to LAC 14"),
    ("replay_reversed", "401873025", "Bi.Robinson left end to TB 34 for 8 yards"),
    ("no_play_penalty", "401873026", "PENALTY on BUF-D.Walker, Encroachment"),
    ("declined_penalty", "401873030", "J.Goff pass incomplete short right to S.LaPorta"),
    ("fumble_lost", "401873034", "D.Maye pass short left to E.Chism to NE 18"),
    ("penalty_wipes_out_pass", "401873036", "(Shotgun) S.Darnold pass incomplete short right to C.Kupp (J.Johnson).PENALTY"),
    ("delay_of_game", "401873036", "PENALTY on CHI, Delay of Game, 5 yards"),
    ("fumble_recovered_and_returned", "401873036", "(Shotgun) C.Williams pass short right to C.Loveland to CHI 21"),
    ("two_point_success", "401873030", "K.Murray pass short middle to T.Hockenson for 8 yards, TOUCHDOWN. TWO-POINT"),
    # Owner review of the play-type clips (OWN-037): the plays each fix is checked against.
    ("pass_deep_tackled_by_safety", "401873036", "(Shotgun) C.Williams pass deep middle to L.Burden"),
    ("interception_intended_receiver", "401873025", "(Shotgun) M.Penix pass short middle intended for J.Dotson"),
    ("defensive_holding_wipes_out_sack", "401873036", "(No Huddle, Shotgun) S.Darnold sacked at CHI 37"),
    ("offensive_pass_interference", "401873036", "S.Darnold pass short left to J.Smith-Njigba pushed ob at CHI 1"),
    ("illegal_contact_declined", "401873036", "(Shotgun) S.Darnold pass short middle to J.Smith-Njigba to CHI 24"),
    ("lateral", "401873023", "(Shotgun) B.Young pass short middle to T.McMillan to CAR 24"),
    ("timeout", "401873036", "Timeout #1 by SEA"),
]


def trim(raw: dict) -> dict:
    play = {k: raw[k] for k in KEEP if k in raw}
    for side in ("start", "end"):
        play[side] = {k: raw[side][k] for k in SPOT if k in raw.get(side, {})}
    play["participants"] = [
        {"athlete": p["athlete"], "type": p["type"]} for p in raw.get("participants", []) if "athlete" in p
    ]
    return play


def main() -> None:
    plays, teams = coverage.captured(Path("data/live-captures"))
    cases, problems = [], []
    for name, event, start in CASES:
        found = [raw for raw in plays[event].values() if raw.get("text", "").startswith(start)]
        if len({raw.get("text") for raw in found}) == 1:
            found = sorted(found, key=lambda raw: float(raw.get("sequenceNumber") or 0))[:1]  # same text twice
        if len(found) != 1:
            problems.append(f"{name}: {len(found)} plays start with {start!r}")
            continue
        home, away, home_code, away_code = teams[event]
        texts = [raw.get("text", "") for raw in plays[event].values()]
        cases.append(
            {
                "name": name,
                "event_id": event,
                "home": home,
                "away": away,
                "home_code": home_code,
                "away_code": away_code,
                "text_codes": sorted(coverage.text_codes_of(texts)),
                "play": trim(found[0]),
            }
        )
    if problems:
        raise SystemExit("\n".join(problems))
    OUT.write_text(
        json.dumps(
            {
                "synthetic": False,
                "projection": "Real ESPN core API plays from the 2026 week 8 captures, trimmed to the "
                "factual play fields the normalizer reads; no league-member data. References are data "
                "and never fetched.",
                "season": 2026,
                "cases": cases,
            },
            indent=1,
        )
        + "\n"
    )
    print(f"Wrote {len(cases)} cases to {OUT}")
    # Their players' 2026 depth chart positions, for the alignment tests (OWN-036).
    import positions as depth

    known = depth.load()
    ids = sorted(
        {
            participant["athlete"]["$ref"].split("/athletes/")[1].split("?")[0]
            for case in cases
            for participant in case["play"]["participants"]
        }
    )
    POSITIONS.write_text(
        json.dumps(
            {
                "synthetic": False,
                "projection": "2026 depth chart positions (nflverse, ESPN-sourced) of the players in "
                "play-facts.examples.json, by ESPN ID, best first; the latest snapshot imported.",
                "positions": {espn_id: list(known[espn_id]) for espn_id in ids if espn_id in known},
            },
            indent=1,
        )
        + "\n"
    )
    print(f"Wrote positions for {sum(1 for i in ids if i in known)} of {len(ids)} players to {POSITIONS}")
    # Each team's starting center, long snapper and quarterback, and its colors (OWN-037).
    TEAMS.write_text(
        json.dumps(
            {
                "synthetic": False,
                "projection": "Each team's rank-1 center, long snapper and quarterback in its latest 2026 "
                "depth chart snapshot imported, as [ESPN ID, text name], and the colors nflverse lists "
                "for it, first to fourth, by nflverse team abbreviation.",
                "units": {team: {k: list(v) for k, v in found.items()} for team, found in depth.units().items()},
                "colors": depth.team_colors(),
            },
            indent=1,
        )
        + "\n"
    )
    print(f"Wrote team units and colors to {TEAMS}")


if __name__ == "__main__":
    main()
