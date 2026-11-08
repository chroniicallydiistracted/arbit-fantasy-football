"""Live action evidence from synthetic NFL and ESPN plays. No tracking inputs."""

import pytest
from arbit_data.live.choreography import choreograph
from arbit_data.live.nfl_api import GameLink, to_live_plays
from arbit_data.live.play_facts import GameTeams, interpret

LINK = GameLink("fictional-game", "900000001", "1", "2", "SEA", "CHI")
TEAMS = GameTeams.build("1", "2", "SEA", "CHI")
IDS = {"nfl-qb": "100", "nfl-target": "101", "nfl-picker": "102", "nfl-back": "103"}


def stat(player, name, role, team, yards=None):
    return {
        "gsisPlayerId": player,
        "gsisPlayerName": name,
        "gsisPlayerJerseyNumber": "01",
        "statType": role,
        "teamId": team,
        "yards": yards,
    }


def converted(kind, text, stats, ids=IDS):
    game = {
        "homeTeam": {"id": "nfl-home"},
        "awayTeam": {"id": "nfl-away"},
        "driveChart": {
            "plays": [
                {
                    "playId": 10,
                    "playType": kind,
                    "quarter": 1,
                    "clockTime": "9:00",
                    "prePlayByPlay": "SEA  KO  SEA 35"
                    if kind == "KICK_OFF"
                    else "SEA  1-10  SEA 35",
                    "yardLine": "SEA 35",
                    "playDescription": text,
                    "playDescriptionWithJerseyNumbers": text,
                    "stats": stats,
                    "playStartTime": "2026-10-01T00:00:00Z",
                    "playEndTime": "2026-10-01T00:00:06Z",
                }
            ]
        },
    }
    (play,) = to_live_plays(game, LINK, ids, 2026)
    return play


def interception(tackler):
    return converted(
        "PASS",
        f"Q.Able pass short left intended for B.Baker INTERCEPTED by D.Dunn at SEA 40. "
        f"D.Dunn to SEA 35 for 5 yards ({tackler[1]}).",
        [
            stat("nfl-qb", "Q.Able", 19, "nfl-home"),
            stat("nfl-qb", "Q.Able", 112, "nfl-home", 5),
            stat("nfl-target", "B.Baker", 115, "nfl-home"),
            stat("nfl-picker", "D.Dunn", 25, "nfl-away", 5),
            stat(*tackler, 79, "nfl-home"),
        ],
    )


@pytest.mark.parametrize(
    ("tackler", "expected_ids"),
    [(("nfl-target", "B.Baker"), ["101"]), (("nfl-back", "R.Firth"), ["101", "103"])],
)
def test_interception_draws_credited_players_once_even_with_a_roster_alias(tackler, expected_ids):
    play = interception(tackler)
    facts = interpret(play, TEAMS)
    names = {"100": "Q.Able", "101": "R.Baker", "102": "D.Dunn", "103": "R.Firth"}
    script = choreograph(
        facts, "synthetic", names=names, positions={"101": ("WR",), "103": ("RB",)}
    )
    assert script is not None
    actors = [a for a in script.actors if a.role in ("receiver", "tackler")]
    assert sorted(a.espn_id or "" for a in actors) == expected_ids
    receiver = next(a for a in actors if a.role == "receiver")
    assert receiver.espn_id == "101"
    interceptor = next(a for a in script.actors if a.role == "interceptor")
    possession = next(
        s.start for s in script.ball if s.state == "held" and s.actor == interceptor.key
    )
    if tackler[0] == "nfl-target":
        assert any(s.pose == "wrap" and s.start > possession for s in receiver.segments)
    else:
        assert all(s.pose != "wrap" for s in receiver.segments)


def test_nfl_evidence_preserves_unmapped_identity_and_reported_zero_air_yards():
    play = converted(
        "PASS",
        "Q.Able pass short left to U.Unknown to SEA 40 for 5 yards.",
        [
            stat("nfl-qb", "Q.Able", 15, "nfl-home", 5),
            stat("nfl-qb", "Q.Able", 111, "nfl-home", 0),
            stat("nfl-unmapped", "U.Unknown", 115, "nfl-home"),
        ],
    )
    assert play.motion_evidence is not None
    assert (play.motion_evidence.air_yards, play.motion_evidence.air_stat_type) == (0, 111)
    target = next(p for p in play.motion_evidence.people if "intendedReceiver" in p.roles)
    assert (target.source_id, target.espn_id, target.team_id, target.name) == (
        "nfl-unmapped",
        None,
        "1",
        "U.Unknown",
    )


def test_corrected_kick_preserves_return_and_two_possession_changes():
    from arbit_data.live.actions import sequence

    text = "Q.Able kicks 60 yards from SEA 35 to CHI 5. D.Dunn to CHI 30 for 25 yards (B.Baker)."
    play = converted(
        "KICK_OFF",
        text
        + " Seattle challenged the ruling, and the play was REVERSED. "
        + text
        + " FUMBLES (B.Baker), RECOVERED by SEA-B.Baker at CHI 31.",
        [
            stat("nfl-qb", "Q.Able", 41, "nfl-home", 60),
            stat("nfl-picker", "D.Dunn", 45, "nfl-away", 25),
            stat("nfl-picker", "D.Dunn", 52, "nfl-away"),
            stat("nfl-target", "B.Baker", 91, "nfl-home"),
            stat("nfl-target", "B.Baker", 59, "nfl-home", 0),
        ],
    )
    actions = sequence(play, interpret(play, TEAMS))
    assert actions.review == "reversed"
    assert [step.kind for step in actions.steps] == [
        "kick",
        "arrival",
        "possession",
        "advance",
        "contact",
        "loose",
        "recovery",
        "dead",
    ]
    assert [
        (s.team_id, s.actor, s.spot.value)
        for s in actions.steps
        if s.kind in ("kick", "possession", "advance", "loose", "recovery")
    ] == [
        ("1", "espn:100", 35),
        ("2", "espn:102", 95),
        ("2", "espn:102", 70),
        ("2", "espn:102", 70),
        ("1", "espn:101", 69),
    ]
    assert actions.duration.value == 6
    assert all(step.seconds.value is None for step in actions.steps[1:-1])


def test_intended_target_and_tackler_reference_the_same_action_actor():
    from arbit_data.live.actions import sequence

    play = interception(("nfl-target", "B.Baker"))
    actions = sequence(play, interpret(play, TEAMS))
    assert [s.kind for s in actions.steps] == [
        "snap",
        "release",
        "arrival",
        "possession",
        "advance",
        "contact",
        "dead",
    ]
    assert actions.steps[1].target == "espn:101"
    assert actions.steps[3].actor == "espn:102"
    assert actions.steps[5].actor == "espn:101"
    assert len([p for p in actions.people if p.espn_id == "101"]) == 1


def test_missing_espn_elapsed_time_is_unknown():
    from arbit_data.live.actions import sequence

    play = interception(("nfl-back", "R.Firth")).model_copy(
        update={
            "source": None,
            "nfl": None,
            "motion_evidence": None,
            "snap_at": None,
            "whistle_at": None,
        }
    )
    actions = sequence(play, interpret(play, TEAMS))
    assert actions.duration.value is None
    assert actions.duration.confidence == "unknown"
    assert actions.steps[-1].seconds.value is None


def test_next_snap_does_not_supply_an_unreported_physical_endpoint():
    from arbit_data.live.actions import sequence
    from arbit_data.live.contracts import FieldPoint

    play = converted(
        "RUSH",
        "R.Firth right tackle.",
        [stat("nfl-back", "R.Firth", 10, "nfl-home")],
    ).model_copy(update={"end": FieldPoint(team_id="1", yard_line=64)})
    actions = sequence(play, interpret(play, TEAMS))
    assert actions.next_state.yard_line == 64
    advance = next(s for s in actions.steps if s.kind == "advance")
    assert advance.spot.value is None
    assert advance.spot.confidence == "unknown"


def test_shared_tackle_keeps_both_credits_without_picking_a_primary():
    from arbit_data.live.actions import sequence

    play = converted(
        "RUSH",
        "R.Firth right tackle to SEA 38 for 3 yards (D.Dunn; B.Baker).",
        [
            stat("nfl-back", "R.Firth", 10, "nfl-home", 3),
            stat("nfl-picker", "D.Dunn", 82, "nfl-away"),
            stat("nfl-target", "B.Baker", 82, "nfl-away"),
        ],
    )
    actions = sequence(play, interpret(play, TEAMS))
    contact = next(step for step in actions.steps if step.kind == "contact")
    assert contact.actor is None
    assert set(contact.actors) == {"espn:101", "espn:102"}
