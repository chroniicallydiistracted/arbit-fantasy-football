"""The nflverse field catalog: every imported field has one recorded use (ADR-006, OWN-061)."""

import json

import pytest
from arbit_model.fields import (
    RULES,
    USES,
    Observation,
    build_catalog,
    catalog_family,
    classify,
    load_catalog,
    render,
    unclassified,
)

CATALOG = load_catalog()
ENTRIES = [
    (family, name, entry)
    for family, fields in CATALOG["fields"].items()
    for name, entry in fields.items()
]


def obs(family, key, *columns, seasons=(), rows=10, missing=None):
    return Observation(
        family=family,
        logical_key="nflverse/nflverse-data/" + key,
        columns=tuple((c, "string") for c in columns),
        seasons=seasons,
        row_count=rows,
        missing=missing or {},
    )


def test_committed_catalog_matches_the_rules_field_by_field():
    drift = [
        (family, name)
        for family, name, entry in ENTRIES
        if (rule := classify(family, name)) is None
        or (rule.id, rule.use) != (entry["rule"], entry["use"])
    ]
    assert drift == []
    assert CATALOG["summary"]["fields"] == len(ENTRIES)
    assert sum(CATALOG["summary"]["byUse"].values()) == len(ENTRIES)


def test_every_rule_is_used_and_states_its_reason():
    used = {entry["rule"] for _, _, entry in ENTRIES}
    assert {rule.id for rule in RULES} == used
    assert set(CATALOG["rules"]) == used
    for rule in RULES:
        assert rule.use in USES and len(rule.reason) > 10


def test_no_other_providers_fantasy_or_projection_data_is_usable():
    for family, name, entry in ENTRIES:
        if name.startswith("fantasy_points") or family in (
            "ff_opportunity",
            "dynastyprocess",
            "misc/espn_draft_player_probs",
            "misc/espn_draft_position_probs",
        ):
            assert entry["use"] == "excluded", (family, name)
    # The DynastyProcess directory only joins identifiers.
    directory = CATALOG["fields"]["ff_playerids"]
    assert {e["use"] for e in directory.values()} == {"identity", "excluded"}
    assert directory["age"]["use"] == "excluded"


def test_betting_lines_wait_for_the_ablation_and_observed_weather_is_history():
    lines = [e for f, n, e in ENTRIES if e["rule"] == "betting-lines"]
    assert {e["use"] for e in lines} == {"excluded"}
    assert CATALOG["rules"]["betting-lines"]["decision"] == "OWN-067"
    assert CATALOG["fields"]["schedules"]["spread_line"]["use"] == "excluded"
    assert CATALOG["fields"]["pbp"]["vegas_wp"]["use"] == "excluded"
    # R-063 as amended (OWN-066 A2): observed weather informs later games only.
    for family in ("schedules", "pbp"):
        assert CATALOG["fields"][family]["temp"]["use"] == "history"
        assert CATALOG["fields"][family]["wind"]["use"] == "history"


def test_participation_informs_only_later_seasons_and_snapshots_apply_as_imported():
    assert CATALOG["fields"]["pbp_participation"]["route"]["use"] == "earlier_seasons"
    assert CATALOG["fields"]["players"]["status"]["use"] == "as_imported"
    assert CATALOG["fields"]["draft_picks"]["w_av"]["use"] == "as_imported"
    assert CATALOG["fields"]["weekly_rosters"]["status"]["use"] == "pre_game"


# ADR-007 A2: no field is kept from the Model because it arrives late. Every remaining exclusion
# is a policy, and adding one is a reviewed decision, not a side effect of a rule edit.
POLICY_EXCLUSIONS = {
    "betting-lines": "OWN-067",
    "dynastyprocess-values": "OWN-061",
    "espn-draft-projections": "OWN-061",
    "ffopportunity": "OWN-061",
    "generic-fantasy-points": "OWN-061",
    "id-directory-facts": "OWN-061",
    "legacy-player-stats": None,  # a duplicate release of stats_player and stats_team
    "pbp-free-text": None,  # an unverified second source of structured facts
    "release-tests": None,  # nflverse's pipeline test assets, not football data
}


def test_every_exclusion_is_a_policy_and_none_is_for_timing():
    excluded = {rule.id: rule.decision for rule in RULES if rule.use == "excluded"}
    assert excluded == POLICY_EXCLUSIONS
    assert CATALOG["summary"]["byUse"]["outcome"] == 0


def test_a_new_upstream_field_is_reported_and_cannot_be_catalogued_silently():
    new = obs("pbp", "pbp/play_by_play_2026", "play_id", "new_tracking_metric", seasons=(2026,))

    assert unclassified(CATALOG, [new]) == [("pbp", "new_tracking_metric")]
    with pytest.raises(ValueError, match="UNCLASSIFIED_FIELDS: pbp.new_tracking_metric"):
        build_catalog([new])


def test_misc_tables_are_catalogued_apart_because_their_columns_share_names():
    lateral = obs("misc", "misc/multiple_lateral_yards", "type", "yards")
    draft = obs("misc", "misc/espn_draft_player_probs", "type", "p")

    assert catalog_family("misc", lateral.logical_key) == "misc/multiple_lateral_yards"
    built = build_catalog([lateral, draft])
    assert built["fields"]["misc/multiple_lateral_yards"]["type"]["use"] == "history"
    assert built["fields"]["misc/espn_draft_player_probs"]["type"]["use"] == "excluded"


def test_first_season_skips_empty_columns_and_reads_a_season_from_the_file_name():
    old = obs(
        "pbp",
        "pbp/play_by_play_2005",
        "air_yards",
        "epa",
        seasons=(2005,),
        missing={"air_yards": 10},
    )
    new = obs("pbp", "pbp/play_by_play_2006", "air_yards", "epa", missing={"air_yards": 3})
    span = obs("schedules", "schedules/games", "roof", seasons=(1999, 2000))

    built = build_catalog([old, new, span], multi_season_first={(span.logical_key, "roof"): 1999})
    assert built["fields"]["pbp"]["air_yards"]["firstSeason"] == 2006
    assert built["fields"]["pbp"]["epa"]["firstSeason"] == 2005
    assert built["fields"]["pbp"]["air_yards"]["tables"] == ["play_by_play_{season}"]
    assert built["fields"]["schedules"]["roof"]["firstSeason"] == 1999


def test_rendered_catalog_is_the_same_json_one_field_per_line():
    built = build_catalog([obs("schedules", "schedules/games", "roof", "temp", "spread_line")])
    text = render(built)

    assert json.loads(text) == built
    assert sum('"roof": {' in line for line in text.splitlines()) == 1
