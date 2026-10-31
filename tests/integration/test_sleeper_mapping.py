from datetime import UTC, datetime, timedelta

from arbit_core.identity import ProviderRef
from arbit_data.identities import resolve_native
from arbit_data.schema import entity_alias
from sqlalchemy import func, select

T = datetime(2026, 10, 31, tzinfo=UTC)


def test_supplemental_join_uses_only_existing_ids_and_never_mutates_aliases(uow):
    from arbit_data.sleeper.mapping import identity_coverage
    from arbit_data.sleeper.reader import normalize_sleeper

    with uow.engine.begin() as c:
        known = resolve_native(
            c,
            [ProviderRef(provider="espn", entity_kind="athlete", external_id="123")],
            T - timedelta(days=1),
            "a" * 64,
        )
        resolve_native(
            c,
            [ProviderRef(provider="gsis", entity_kind="athlete", external_id="00-0012345")],
            T - timedelta(days=1),
            "b" * 64,
        )
        before = c.scalar(select(func.count()).select_from(entity_alias))
    data = normalize_sleeper(
        "sleeper.players",
        {
            "101": {"player_id": "101", "espn_id": "123"},
            "102": {"player_id": "102", "espn_id": "123", "gsis_id": "00-0012345"},
            "CAR": {"player_id": "CAR", "position": "DEF"},
        },
    )
    report = identity_coverage(uow, data, T)
    assert report["counts"]["conflict"] == 2  # reused directory ID plus disagreement
    assert report["counts"]["excluded"] == 1
    with uow.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(entity_alias)) == before
    single = normalize_sleeper("sleeper.players", {"101": {"player_id": "101", "espn_id": "123"}})
    linked = identity_coverage(uow, single, T)
    assert linked["records"][0]["entity_id"] == str(next(iter(known.values())))
    assert identity_coverage(uow, single, T - timedelta(days=2))["counts"]["unresolved"] == 1
