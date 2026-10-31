"""Gridiron prerequisite selection only: no downloader, hotlink or image-serving path."""

from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Self
from urllib.parse import unquote, urlsplit

from arbit_core.identity import require_aware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


class AssetContext(AssetModel):
    kind: Literal["field", "uniform"]
    season: int = Field(strict=True, ge=1920, le=2100)
    season_type: Literal["pre", "regular", "post"]
    week: int = Field(strict=True, ge=1, le=25)
    event_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    nfl_team_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    venue_id: str | None = Field(default=None, min_length=1, max_length=64)
    neutral_site: bool | None = None


class Permission(AssetModel):
    status: Literal["pending", "granted", "denied"] = "pending"
    kind: Literal["field", "uniform"]
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    evidence: str | None = Field(default=None, min_length=1, max_length=2048)
    uses: tuple[Literal["local_display", "local_cache", "redistribute", "adapt"], ...] = ()

    @model_validator(mode="after")
    def valid_times(self) -> Self:
        for value in (self.granted_at, self.expires_at):
            if value is not None:
                require_aware(value)
        if self.granted_at and self.expires_at and self.expires_at <= self.granted_at:
            raise ValueError("INVALID_PERMISSION_PERIOD")
        return self


class AssetRecord(AssetModel):
    asset_id: str = Field(min_length=1, max_length=128)
    context: AssetContext
    variant: str | None = Field(default=None, min_length=1, max_length=256)
    source_page: str
    image_url: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    media_type: Literal["image/png", "image/gif", "image/jpeg", "image/webp"] | None = None
    width: int | None = Field(default=None, strict=True, gt=0, le=16000)
    height: int | None = Field(default=None, strict=True, gt=0, le=16000)
    variant_verified: bool = False
    verified_at: datetime | None = None
    variant_evidence: str | None = Field(default=None, min_length=1, max_length=2048)
    pattern_evidence: str | None = Field(default=None, min_length=1, max_length=2048)
    attribution: str | None = Field(default=None, min_length=1, max_length=2048)
    permission: Permission

    @field_validator("source_page", "image_url")
    @classmethod
    def public_gridiron_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        u = urlsplit(value)
        path = unquote(unquote(u.path))
        if (
            u.scheme != "https"
            or u.netloc not in ("gridiron-uniforms.com", "www.gridiron-uniforms.com")
            or u.fragment
            or not path.startswith(("/GUD/", "/fields/"))
            or ".." in path.split("/")
            or any(ord(x) < 33 for x in value)
        ):
            raise ValueError("INVALID_GRIDIRON_URL")
        return value

    @model_validator(mode="after")
    def valid_observation(self) -> Self:
        if self.verified_at is not None:
            require_aware(self.verified_at)
        return self


class AssetManifest(AssetModel):
    format: Literal["gridiron-assets-v1"] = "gridiron-assets-v1"
    assets: tuple[AssetRecord, ...] = ()

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(self.assets) > 4096 or len({a.asset_id for a in self.assets}) != len(self.assets):
            raise ValueError("INVALID_ASSET_IDS")
        return self


def load_manifest(path: Path) -> AssetManifest:
    with path.open("rb") as source:
        body = source.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("ASSET_MANIFEST_TOO_LARGE")
    return AssetManifest.model_validate_json(body)


def prerequisite_gaps(asset: AssetRecord, as_of: datetime) -> list[str]:
    require_aware(as_of)
    asset = AssetRecord.model_validate(asset.model_dump())
    gaps = []
    if (
        not asset.variant_verified
        or not asset.variant
        or not asset.variant_evidence
        or not asset.pattern_evidence
    ):
        gaps.append("VARIANT_OR_PATTERN_UNVERIFIED")
    if asset.verified_at is None or asset.verified_at > as_of:
        gaps.append("VARIANT_NOT_OBSERVED_BY_CUTOFF")
    if not all(
        (
            asset.image_url,
            asset.sha256,
            asset.media_type,
            asset.width,
            asset.height,
            asset.attribution,
        )
    ):
        gaps.append("IMAGE_METADATA_OR_ATTRIBUTION_MISSING")
    grant = asset.permission
    if (
        grant.status != "granted"
        or not grant.evidence
        or grant.kind != asset.context.kind
        or grant.granted_at is None
        or grant.granted_at > as_of
        or grant.expires_at is not None
        and grant.expires_at <= as_of
        or not {"local_display", "local_cache"} <= set(grant.uses)
    ):
        gaps.append("REUSE_PERMISSION_UNVERIFIED_OR_EXPIRED")
    return gaps


def resolve_asset(
    context: AssetContext, records: list[AssetRecord], as_of: datetime
) -> dict[str, Any]:
    require_aware(as_of)
    context = AssetContext.model_validate(context.model_dump())
    if context.venue_id is None or context.neutral_site is None:
        return {
            "status": "fallback",
            "reason": "CONTEXT_UNVERIFIED",
            "label": "Generic field or uniform; exact game variant unverified",
            "asset": None,
            "local_asset_ready": False,
        }
    candidates = [a for a in records if a.context == context and not prerequisite_gaps(a, as_of)]
    if len(candidates) != 1:
        return {
            "status": "fallback",
            "reason": "AMBIGUOUS_ASSET" if len(candidates) > 1 else "VERIFIED_ASSET_UNAVAILABLE",
            "label": "Generic field or uniform; exact game variant unverified",
            "asset": None,
            "local_asset_ready": False,
        }
    return {
        "status": "eligible_metadata",
        "asset": candidates[0].model_dump(mode="json"),
        "local_asset_ready": False,
        "limitations": [
            "Metadata prerequisites only. Local image bytes, media decoding and serving require separate M6 validation."
        ],
    }
