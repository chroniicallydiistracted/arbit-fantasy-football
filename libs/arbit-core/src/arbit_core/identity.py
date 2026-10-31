"""Temporal, provider-scoped identity resolution. Names are never matching keys."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EntityKind = Literal[
    "athlete", "nfl_team", "defense_unit", "fantasy_team", "manager", "fantasy_matchup"
]


def require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")


def validate_period(start: datetime, end: datetime | None) -> None:
    require_aware(start)
    if end is not None:
        require_aware(end)
        if end <= start:
            raise ValueError("validity end must be after start")


class ProviderRef(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    provider: str = Field(min_length=1)
    entity_kind: EntityKind
    external_id: str = Field(min_length=1)
    scope: str = Field(default="global", min_length=1)


@dataclass(frozen=True)
class Alias:
    ref: ProviderRef
    entity_id: UUID
    valid_from: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        validate_period(self.valid_from, self.valid_to)


@dataclass(frozen=True)
class Affiliation:
    entity_id: UUID
    team_id: UUID
    valid_from: datetime
    valid_to: datetime | None = None

    def __post_init__(self) -> None:
        validate_period(self.valid_from, self.valid_to)


@dataclass(frozen=True)
class ResolvedIdentity:
    entity_id: UUID
    entity_kind: EntityKind


@dataclass(frozen=True)
class UnresolvedIdentity:
    reason: str = "no_verified_alias"
    entity_id: None = None


class IdentityMap:
    def __init__(self, aliases: Iterable[Alias], affiliations: Iterable[Affiliation] = ()) -> None:
        self._aliases: dict[ProviderRef, list[Alias]] = defaultdict(list)
        self._affiliations: dict[UUID, list[Affiliation]] = defaultdict(list)
        for alias in aliases:
            self._aliases[alias.ref].append(alias)
        for affiliation in affiliations:
            self._affiliations[affiliation.entity_id].append(affiliation)
        for alias_group in self._aliases.values():
            ordered = sorted(alias_group, key=lambda item: item.valid_from)
            for previous, current in pairwise(ordered):
                if previous.valid_to is None or previous.valid_to > current.valid_from:
                    raise ValueError("overlapping verified aliases")
        for affiliation_group in self._affiliations.values():
            ordered_affiliations = sorted(affiliation_group, key=lambda item: item.valid_from)
            for previous_affiliation, current_affiliation in pairwise(ordered_affiliations):
                if (
                    previous_affiliation.valid_to is None
                    or previous_affiliation.valid_to > current_affiliation.valid_from
                ):
                    raise ValueError("overlapping team affiliations")

    def resolve_identity(
        self, ref: ProviderRef, as_of: datetime
    ) -> ResolvedIdentity | UnresolvedIdentity:
        require_aware(as_of)
        for alias in self._aliases.get(ref, []):
            if alias.valid_from <= as_of and (alias.valid_to is None or as_of < alias.valid_to):
                return ResolvedIdentity(alias.entity_id, ref.entity_kind)
        return UnresolvedIdentity()

    def team_at(self, entity_id: UUID, as_of: datetime) -> UUID | None:
        require_aware(as_of)
        for item in self._affiliations.get(entity_id, []):
            if item.valid_from <= as_of and (item.valid_to is None or as_of < item.valid_to):
                return item.team_id
        return None
