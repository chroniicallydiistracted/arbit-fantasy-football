"""Explicit fictional two-member browser rehearsal, isolated from all real data.

Run with ARBIT_ENV=test ARBIT_AUTH_MODE=fixture and a dedicated loopback
ARBIT_DATABASE_URL ending _fixture or _test. ARBIT_PUBLIC_ORIGIN is the browser
origin (including the Vite port). This module never fetches a provider.
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from alembic import command
from alembic.config import Config
from arbit_data.contracts import LeagueSnapshotCandidate, RosterEntry
from arbit_data.db import UnitOfWork
from arbit_data.league import FantasyTeam, LeagueDocument, Manager, Matchup, MatchupSide, Player
from arbit_data.live import store as live_store
from arbit_data.members import (
    account_exists,
    bind_manager,
    create_invitation,
    digest,
    logout,
    sign_in,
)
from arbit_data.schema import (
    current_snapshot,
    league_document,
    rule_version,
    scoring_verification,
    sync_state,
)
from arbit_data.snapshots import publish_snapshot_in_transaction
from sqlalchemy import Engine, create_engine, insert, select

from arbit_api.settings import RuntimeSettings


class FixtureSafetyError(ValueError):
    pass


# Fictional NFL ESPN IDs well outside the real range.
FIXTURE_HOME, FIXTURE_AWAY, FIXTURE_EVENT = "9901", "9902", "990000001"


def fixture_game(home_score: str | None, phase: str = "in_progress") -> dict[str, object]:
    return {
        "event_id": FIXTURE_EVENT,
        "season": 2026,
        "date": "2026-11-01T17:00:00Z",
        "home_team_id": FIXTURE_HOME,
        "away_team_id": FIXTURE_AWAY,
        "home_score": home_score,
        "away_score": "3",
        "source_status": "FICTIONAL",
        "phase": phase,
        "completed": phase == "final",
        "period": 2,
        "clock": "4:12",
        "neutral_site": False,
        "status_detail": "4:12 - 2nd",
        "home_line": {
            "color": "1b6e3c",
            "alternate_color": "f2c230",
            "record": "5-2",
            "periods": ["0", home_score or "0"],
        },
        "away_line": {
            "color": "7a1f2b",
            "alternate_color": "e8e8e8",
            "record": "3-4",
            "periods": ["3", "0"],
        },
        "situation": {
            "down": 3,
            "distance": 7,
            "yard_line": 38,
            "possession_team_id": FIXTURE_HOME,
            "field_text": "FIC 38",
            "short_text": "3rd & 7",
            "red_zone": False,
            "home_timeouts": 3,
            "away_timeouts": 1,
            "last_play": {
                "kind_text": "Rush",
                "text": "Fictional runner up the middle for 3 yards.",
                "yards": 3,
            },
        },
        "venue": {"name": "Fixture Field", "city": "Testville", "state": "TS", "indoor": False},
        "weather": {"temperature": 61, "condition": "Clear"},
        "broadcast": ["TEST"],
        "leaders": [
            {
                "category": "PASS",
                "name": "Q. Fiction",
                "team_id": FIXTURE_HOME,
                "line": "11/16, 121 YDS",
            },
        ],
        "recommendations_enabled": False,
        "fantasy_scoring": "not_calculated; ESPN Fantasy remains authoritative",
    }


FIXTURE_DETAIL = {
    "drives": [
        {
            "team_id": FIXTURE_AWAY,
            "result": "Field goal",
            "plays": 8,
            "yards": 41,
            "elapsed": "4:02",
            "start": "TST 25",
            "end": "FIC 34",
            "scored": True,
            "current": False,
        },
        {
            "team_id": FIXTURE_HOME,
            "result": None,
            "plays": 3,
            "yards": 13,
            "elapsed": "1:10",
            "start": "FIC 25",
            "end": None,
            "scored": None,
            "current": True,
        },
    ],
    "win_probability": [{"play_id": str(n), "home": 0.5 + n / 50} for n in range(12)],
    "team_stats": [
        {"key": "totalYards", "label": "Total Yards", "home": "121", "away": "96"},
        {"key": "turnovers", "label": "Turnovers", "home": "0", "away": "1"},
    ],
}


def publish_fixture_score(engine: Engine, home_score: str) -> None:
    """Publish a fictional scoreboard change, exactly as the worker would."""
    if not (engine.url.database or "").endswith(("_fixture", "_test")):
        raise FixtureSafetyError("Fictional live data requires a dedicated fixture database")
    live_store.publish_scoreboard(
        UnitOfWork(engine),
        {"season": 2026, "season_type": 2, "week": 8, "games": [fixture_game(home_score)]},
        datetime.now(UTC),
    )
    live_store.publish_summary(
        UnitOfWork(engine), FIXTURE_EVENT, {}, datetime.now(UTC), FIXTURE_DETAIL
    )


def seed(settings: RuntimeSettings, engine: Engine) -> None:
    if (
        settings.auth_mode != "fixture"
        or settings.environment != "test"
        or engine.url.host not in ("127.0.0.1", "localhost", "::1")
        or not (engine.url.database or "").endswith(("_fixture", "_test"))
    ):
        raise FixtureSafetyError("Fictional preview requires explicit isolated fixture settings")
    migration = Config("alembic.ini")
    with engine.begin() as c:
        migration.attributes["connection"] = c
        command.upgrade(migration, "head")
    uow = UnitOfWork(engine)
    now = datetime.now(UTC)
    rule_hash = digest("arbit-fictional-browser-fixture-v1")
    manager_one, manager_two, comanager = UUID(int=101), UUID(int=102), UUID(int=103)
    team_one, team_two = UUID(int=201), UUID(int=202)
    with engine.begin() as c:
        existing = c.scalar(
            select(current_snapshot.c.snapshot_id).where(current_snapshot.c.season == 2026)
        )
        if existing:
            previous_hash = c.scalar(
                select(league_document.c.rules_hash).where(
                    league_document.c.snapshot_id == existing
                )
            )
            if previous_hash != rule_hash:
                raise FixtureSafetyError("Refusing a database containing another league snapshot")
        else:
            teams = tuple(
                FantasyTeam(
                    id=team,
                    name=name,
                    abbreviation=abbr,
                    managers=managers,
                    primary_manager=managers[0],
                    wins=wins,
                    losses=7 - wins,
                    ties=0,
                    points_for=Decimal(points),
                    points_against=Decimal("712.75"),
                    waiver_rank=index + 1,
                    playoff_seed=index + 1,
                )
                for index, (team, name, abbr, managers, wins, points) in enumerate(
                    [
                        (
                            team_one,
                            "Fictional Juniper Club",
                            "JUN",
                            (manager_one, comanager),
                            5,
                            "834.50",
                        ),
                        (team_two, "Fictional Copper Owls", "OWL", (manager_two,), 4, "802.25"),
                    ]
                )
            )
            players: list[Player] = []
            slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DST", "BENCH", "BENCH", "IR"]
            positions = ["QB", "RB", "RB", "WR", "WR", "TE", "RB", "K", "DST", "WR", "QB", "RB"]
            first_names = [
                "Avery",
                "Rowan",
                "Morgan",
                "Cameron",
                "Riley",
                "Dakota",
                "Emerson",
                "Finley",
                "Fictional",
                "Hayden",
                "Jordan",
                "Parker",
            ]
            for t, suffix in [(team_one, "Juniper"), (team_two, "Copper")]:
                for i, (slot, pos, name) in enumerate(
                    zip(slots, positions, first_names, strict=True)
                ):
                    players.append(
                        Player(
                            id=UUID(int=1000 + t.int * 100 + i),
                            kind="defense_unit" if pos == "DST" else "athlete",
                            display_name=f"{name} {suffix}"
                            if pos != "DST"
                            else f"{suffix} Defense",
                            position=cast(Literal["QB", "RB", "WR", "TE", "K", "DST"], pos),
                            nfl_team_id=None,
                            eligible_slots=(slot,),
                            active=True,
                            injured=i == 11,
                            injury_status="OUT" if i == 11 else None,
                            injury="out" if i == 11 else None,
                            availability="owned",
                            team_id=t,
                            lineup_slot=slot,
                            lineup_locked=i == 0,
                            roster_locked=i == 0,
                            trade_locked=False,
                            official_current_points=None,
                        )
                    )
            for i in range(10):
                players.append(
                    Player(
                        id=UUID(int=4000 + i),
                        kind="athlete",
                        display_name=f"Fictional Prospect {i + 1}",
                        position="WR",
                        nfl_team_id=None,
                        eligible_slots=("WR", "FLEX", "BENCH"),
                        active=True,
                        injured=False,
                        injury_status=None,
                        availability="free_agent",
                        team_id=None,
                        lineup_slot=None,
                        lineup_locked=False,
                        roster_locked=False,
                        trade_locked=False,
                        official_current_points=None,
                    )
                )
            document = LeagueDocument(
                season=2026,
                scoring_period=8,
                matchup_period=8,
                rules_hash=rule_hash,
                managers=(
                    Manager(id=manager_one, display_name="Fictional manager one"),
                    Manager(id=manager_two, display_name="Fictional manager two"),
                    Manager(id=comanager, display_name="Fictional co-manager"),
                ),
                teams=teams,
                nfl_teams=(),
                players=tuple(players),
                matchups=(
                    Matchup(
                        id=UUID(int=701),
                        matchup_period=7,
                        scoring_periods=(7,),
                        home=MatchupSide(team_id=team_one, official_points=Decimal("128.25")),
                        away=MatchupSide(team_id=team_two, official_points=Decimal("119.50")),
                        winner="home",
                    ),
                    Matchup(
                        id=UUID(int=801),
                        matchup_period=8,
                        scoring_periods=(8,),
                        # In progress: a live total for a side that has played, none before.
                        home=MatchupSide(
                            team_id=team_one, official_points=None, live_points=Decimal("64.30")
                        ),
                        away=MatchupSide(team_id=team_two, official_points=None),
                    ),
                ),
                draft_completed=True,
                draft_in_progress=False,
                draft_picks=(),
            )
            candidate = LeagueSnapshotCandidate(
                league_id="1729878439",
                season=2026,
                observed_at=now,
                complete=True,
                rules_hash=rule_hash,
                manifest_hash=digest("fictional-preview-not-provider-evidence"),
                teams=(team_one, team_two),
                roster=tuple(
                    RosterEntry(entity_id=p.id, team_id=p.team_id, slot=p.lineup_slot or "BENCH")
                    for p in players
                    if p.team_id
                ),
                available=tuple(p.id for p in players if p.team_id is None),
            )
            c.execute(
                insert(scoring_verification).values(
                    key=rule_hash,
                    season=2026,
                    verified_at=now,
                    manifest_hash=candidate.manifest_hash,
                    payload={"synthetic": True, "not_provider_evidence": True},
                )
            )
            c.execute(
                insert(rule_version).values(
                    hash=rule_hash,
                    season=2026,
                    scoring_key=rule_hash,
                    payload={"synthetic": True, "recommendations_enabled": False},
                )
            )
            snapshot = publish_snapshot_in_transaction(c, candidate, now=now)
            c.execute(
                insert(league_document).values(
                    snapshot_id=snapshot.id,
                    state_hash=document.state_hash,
                    rules_hash=rule_hash,
                    kind="initial",
                    changes={"synthetic": True},
                    payload=document.model_dump(mode="json"),
                    published_at=now,
                )
            )
            c.execute(
                insert(sync_state).values(
                    season=2026,
                    next_due_at=now + timedelta(days=365),
                    paused=True,
                    consecutive_failures=0,
                    last_attempt_at=now,
                    last_success_at=now,
                    last_snapshot_id=snapshot.id,
                    last_manifest_hash=candidate.manifest_hash,
                )
            )
    for name, manager in [("one", manager_one), ("two", manager_two)]:
        invite = (
            None
            if account_exists(uow, "https://fiction.invalid", name)
            else create_invitation(uow, "https://fiction.invalid", f"{name}@fiction.invalid")
        )
        token, account = sign_in(
            uow,
            "https://fiction.invalid",
            name,
            f"{name}@fiction.invalid",
            True,
            invitation=invite,
            display_name=f"Fictional member {name}",
        )
        bind_manager(uow, account["id"], manager, 2026, account["id"])
        logout(uow, token)
    live_store.publish_directory(
        uow,
        live_store.Directory(
            (
                live_store.TeamEntry(FIXTURE_HOME, "FIC", "Fictional", "Falcons", 5),
                live_store.TeamEntry(FIXTURE_AWAY, "TST", "Testing", "Tigers", 9),
            )
        ),
        2026,
        now,
        digest("arbit-fictional-nfl-directory-v1"),
    )
    publish_fixture_score(engine, "7")


if __name__ == "__main__":
    settings = RuntimeSettings()
    if settings.auth_mode != "fixture" or settings.database_url is None:
        raise SystemExit("Set explicit fixture environment and dedicated database settings first")
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "live-score":
            publish_fixture_score(engine, sys.argv[2])
            print("Fictional live score published. No provider proof.")
            raise SystemExit(0)
        seed(settings, engine)
        print(
            "Fictional preview ready: two members, two teams, 34 fictional players. No provider proof."
        )
    finally:
        engine.dispose()
