from datetime import UTC, datetime
from uuid import UUID

import pytest

A = UUID("00000000-0000-4000-8000-000000000001")
B = UUID("00000000-0000-4000-8000-000000000002")
START = datetime(2026, 1, 1, tzinfo=UTC)
CHANGE = datetime(2026, 10, 1, tzinfo=UTC)


def test_preserves_provider_id_and_resolves_only_verified_alias():
    from arbit_core.identity import Alias, IdentityMap, ProviderRef, ResolvedIdentity

    ref = ProviderRef(provider="espn", entity_kind="athlete", external_id="0012")
    identities = IdentityMap([Alias(ref, A, START)])
    assert identities.resolve_identity(ref, START) == ResolvedIdentity(A, "athlete")
    assert ref.external_id == "0012"


def test_same_name_or_other_entity_kind_cannot_be_guessed():
    from arbit_core.identity import Alias, IdentityMap, ProviderRef, UnresolvedIdentity

    ref = ProviderRef(provider="espn", entity_kind="defense_unit", external_id="0012")
    other = ProviderRef(provider="espn", entity_kind="athlete", external_id="0012")
    identities = IdentityMap([Alias(ref, A, START)])
    assert isinstance(identities.resolve_identity(other, START), UnresolvedIdentity)
    assert isinstance(
        identities.resolve_identity(
            ProviderRef(provider="nflverse", entity_kind="athlete", external_id="Alex Sample"),
            START,
        ),
        UnresolvedIdentity,
    )


def test_alias_validity_is_half_open_and_overlaps_are_rejected():
    from arbit_core.identity import Alias, IdentityMap, ProviderRef

    ref = ProviderRef(provider="espn", entity_kind="athlete", external_id="0012")
    identities = IdentityMap([Alias(ref, A, START, CHANGE), Alias(ref, B, CHANGE)])
    assert identities.resolve_identity(ref, START).entity_id == A
    assert identities.resolve_identity(ref, CHANGE).entity_id == B
    with pytest.raises(ValueError, match="overlap"):
        IdentityMap([Alias(ref, A, START), Alias(ref, B, CHANGE)])


def test_dated_team_affiliation_and_unknown_timestamp():
    from arbit_core.identity import Affiliation, IdentityMap, ProviderRef

    identities = IdentityMap([], [Affiliation(A, A, START, CHANGE), Affiliation(A, B, CHANGE)])
    assert identities.team_at(A, START) == A
    assert identities.team_at(A, CHANGE) == B
    with pytest.raises(ValueError, match="timezone"):
        identities.resolve_identity(
            ProviderRef(provider="espn", entity_kind="athlete", external_id="1"),
            datetime(2026, 1, 1),
        )
