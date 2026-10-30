"""Explicit normalized scoring rules. No ESPN category or FFA default is inferred."""

import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scope = Literal["event", "game", "season"]


class ScoringModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", allow_inf_nan=False)


class LinearRule(ScoringModel):
    kind: Literal["linear"] = "linear"
    id: str = Field(min_length=1)
    stat: str = Field(min_length=1)
    rate: Decimal


class ThresholdRule(ScoringModel):
    kind: Literal["threshold"] = "threshold"
    id: str = Field(min_length=1)
    stat: str = Field(min_length=1)
    threshold: Decimal
    points: Decimal


class RangeRule(ScoringModel):
    kind: Literal["range"] = "range"
    id: str = Field(min_length=1)
    stat: str = Field(min_length=1)
    lower: Decimal
    upper: Decimal | None = None
    points: Decimal

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if self.upper is not None and self.upper <= self.lower:
            raise ValueError("range upper must exceed lower")
        return self


class UnsupportedRule(ScoringModel):
    kind: Literal["unsupported"] = "unsupported"
    id: str = Field(min_length=1)
    source_definition: str


Rule = Annotated[
    LinearRule | ThresholdRule | RangeRule | UnsupportedRule, Field(discriminator="kind")
]


class RuleSet(ScoringModel):
    version: str = Field(min_length=1)
    scope: Scope
    quantum: Decimal
    rounding: Literal["half_up", "half_even"]
    rules: tuple[Rule, ...]

    @model_validator(mode="after")
    def valid_rules(self) -> Self:
        if (
            self.quantum <= 0
            or self.quantum > 1
            or self.quantum.normalize().as_tuple().digits != (1,)
        ):
            raise ValueError("quantum must be a power of ten between zero and one")
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("duplicate source rule IDs")
        return self

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class StatLine(ScoringModel):
    scope: Scope
    values: dict[str, Decimal | None]
