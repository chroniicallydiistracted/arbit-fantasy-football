import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

T = datetime(2026, 10, 31, tzinfo=UTC)


def raw_play(id="12301", kind="Rush", seq="10", **extra):
    return {
        "id": id,
        "sequenceNumber": seq,
        "type": {"id": "5", "text": kind},
        "text": "Synthetic play",
        "period": {"number": 1},
        "clock": {"displayValue": "12:00"},
        "start": {"yardsToEndzone": 80, "team": {"id": "1"}},
        "end": {"yardsToEndzone": 70, "team": {"id": "1"}},
        **extra,
    }


def test_actual_play_examples_retain_ids_effects_and_source_authority():
    from arbit_data.live.normalize import normalize_play

    fixture = json.loads(Path("tests/fixtures/live/espn-2026-source.examples.json").read_text())
    plays = [normalize_play(p, fixture["event_id"], fixture["season"]) for p in fixture["plays"]]
    assert {
        "pass",
        "rush",
        "sack",
        "interception",
        "field_goal",
        "fumble",
        "penalty",
        "punt",
        "kickoff",
    } <= {p.kind for p in plays}
    assert all(p.provider_id and p.event_id == fixture["event_id"] for p in plays)
    assert any(p.participants for p in plays)
    assert any("pat" in p.effects for p in plays)


def test_named_sneak_pat_two_point_unknown_and_cancelled_fallbacks():
    from arbit_data.live.normalize import normalize_play

    for text, expected in [
        ("Extra Point Good", "pat"),
        ("Two Point Pass", "two_point"),
        ("Alien Play", "unknown"),
    ]:
        assert normalize_play(raw_play(kind=text), "123", 2026).kind == expected
    assert normalize_play(raw_play(text="Synthetic quarterback sneak"), "123", 2026).kind == "sneak"
    assert normalize_play(
        raw_play(kind="Penalty", text="Synthetic penalty. No Play."), "123", 2026
    ).cancelled


def test_participants_only_parse_expected_public_espn_nfl_scoped_refs():
    from arbit_data.live.normalize import normalize_play

    ref = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/12345?lang=en"
    p = normalize_play(
        raw_play(participants=[{"athlete": {"$ref": ref}, "type": "rusher"}]), "123", 2026
    )
    assert p.participants[0].espn_id == "12345"
    for invalid in [
        ref.replace(".com/", ".pvt/"),
        ref.replace("/2026/", "/2025/"),
        ref.replace("sports.core.api.espn.com", "evil.example"),
    ]:
        with pytest.raises(ValueError):
            normalize_play(raw_play(participants=[{"athlete": {"$ref": invalid}}]), "123", 2026)


def test_turnover_endpoints_keep_separate_frames_and_missing_is_unknown():
    from arbit_data.live.normalize import normalize_play

    p = normalize_play(
        raw_play(
            kind="Pass Interception Return",
            isTurnover=True,
            end={"yardsToEndzone": 10, "team": {"id": "2"}},
        ),
        "123",
        2026,
    )
    assert not p.can_connect_endpoints and p.start.team_id == "1" and p.end.team_id == "2"
    assert normalize_play(raw_play(start={}), "123", 2026).start.yards_to_endzone is None


def test_duplicate_revised_cancelled_late_and_omitted_replay():
    from arbit_data.live.normalize import normalize_play
    from arbit_data.live.replay import PlaySnapshot, merge_observations

    a = normalize_play(raw_play(), "123", 2026)
    b = normalize_play(raw_play(id="12302", seq="2"), "123", 2026)
    first = PlaySnapshot("123", T, (a, b))
    same = merge_observations(first, first)
    assert same.changes == () and [p.provider_id for p in same.snapshot.plays] == ["12302", "12301"]
    corrected = normalize_play(raw_play(kind="Penalty", text="No Play."), "123", 2026)
    changed = merge_observations(first, PlaySnapshot("123", T + timedelta(seconds=1), (corrected,)))
    assert changed.changes[0]["type"] == "cancelled" and len(changed.snapshot.plays) == 2
    assert merge_observations(changed.snapshot, first).ignored_older
    with pytest.raises(ValueError):
        merge_observations(first, PlaySnapshot("999", T, (a,)))


def test_game_status_scope_and_null_scores_are_honest():
    from arbit_data.live.normalize import normalize_game

    event = {
        "id": "123",
        "season": {"year": 2026},
        "competitions": [
            {
                "id": "123",
                "competitors": [{"homeAway": "home", "id": "1"}, {"homeAway": "away", "id": "2"}],
                "status": {
                    "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "completed": False},
                    "period": 5,
                    "displayClock": "1:00",
                },
            }
        ],
    }
    g = normalize_game(event, 2026)
    assert g.phase == "overtime" and g.home_score is None
    for name, phase in [
        ("STATUS_POSTPONED", "postponed"),
        ("STATUS_DELAYED", "delayed"),
        ("STATUS_HALFTIME", "halftime"),
    ]:
        e = deepcopy(event)
        e["competitions"][0]["status"]["type"]["name"] = name
        assert normalize_game(e, 2026).phase == phase
    with pytest.raises(ValueError):
        normalize_game(event, 2027)


def test_collection_checks_page_scope_duplicates_and_counts():
    from arbit_data.live.normalize import normalize_play
    from arbit_data.live.reader import collect_play_pages

    pages = [
        {
            "event_id": "123",
            "count": 2,
            "page_index": 1,
            "page_count": 2,
            "plays": [normalize_play(raw_play(), "123", 2026).model_dump(mode="json")],
        },
        {
            "event_id": "123",
            "count": 2,
            "page_index": 2,
            "page_count": 2,
            "plays": [normalize_play(raw_play(id="12302"), "123", 2026).model_dump(mode="json")],
        },
    ]
    assert len(collect_play_pages(pages, "123", 2026)) == 2
    bad = deepcopy(pages)
    bad[1]["count"] = 3
    with pytest.raises(ValueError):
        collect_play_pages(bad, "123", 2026)
    bad = deepcopy(pages)
    bad[1]["plays"] = deepcopy(pages[0]["plays"])
    with pytest.raises(ValueError):
        collect_play_pages(bad, "123", 2026)


@pytest.mark.parametrize("change", [{"type": 42}, {"participants": [5]}, {"start": "bad"}])
def test_malformed_play_containers_fail_as_validation_errors(change):
    from arbit_data.live.normalize import normalize_play

    with pytest.raises(ValueError):
        normalize_play(raw_play(**change), "123", 2026)


def test_observed_negative_down_sentinel_stays_unknown_with_raw_evidence():
    from arbit_data.live.normalize import normalize_play

    p = normalize_play(raw_play(kind="End Period", start={"down": -1, "distance": 0}), "123", 2026)
    assert p.start.down is None and p.start.source_down == "-1"
    with pytest.raises(ValueError):
        normalize_play(raw_play(start={"down": -2}), "123", 2026)
