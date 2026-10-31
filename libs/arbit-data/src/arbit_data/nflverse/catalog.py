"""Complete published nflverse/ffverse inventory, with every format decision retained."""

import re
from datetime import datetime
from typing import Any, Literal
from urllib.parse import quote, unquote, urlsplit

from arbit_core.identity import require_aware
from pydantic import Field

from arbit_data.contracts import DataModel

CORE_REPO = "nflverse/nflverse-data"
OPPORTUNITY_REPO = "ffverse/ffopportunity"
CORE_FAMILIES = {
    "trades",
    "teams",
    "schedules",
    "stats_team",
    "stats_player",
    "ftn_charting",
    "espn_data",
    "weekly_rosters",
    "players_components",
    "players",
    "pbp_participation",
    "officials",
    "misc",
    "test",
    "draft_picks",
    "contracts",
    "snap_counts",
    "rosters",
    "player_stats",
    "pfr_advstats",
    "pbp",
    "nextgen_stats",
    "injuries",
    "depth_charts",
    "combine",
}
EXTENSIONS = ("parquet", "csv.gz", "csv", "rds", "qs", "json", "txt")
Usage = Literal[
    "statistics", "identity", "reference", "benchmark", "diagnostic", "metadata", "legacy"
]


class Asset(DataModel):
    source_id: str
    repository: str
    release: str
    family: str
    logical_key: str
    filename: str
    format: str
    source_url: str
    size: int = Field(ge=0, le=512 * 1024 * 1024)
    source_updated_at: datetime | None
    source_created_at: datetime | None
    provider_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    git_blob_sha1: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    selected: bool
    disposition: str
    usage: Usage
    license: str
    attribution: str
    availability_note: str


class Catalog(DataModel):
    format: Literal["nflverse-catalog-v1"] = "nflverse-catalog-v1"
    observed_at: datetime
    assets: tuple[Asset, ...]
    sources: tuple[str, ...]


def _parts(filename: str) -> tuple[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_+.-]{1,180}", filename) or ".." in filename:
        raise ValueError("INVALID_ASSET_NAME")
    for ext in EXTENSIONS:
        if filename.endswith("." + ext):
            return filename[: -len(ext) - 1], ext
    return filename, "opaque"


def _usage(family: str, stem: str) -> Usage:
    if stem.startswith("timestamp") or stem == "data_releases":
        return "metadata"
    if family == "test":
        return "diagnostic"
    if family.startswith("ff_") or family == "dynastyprocess":
        return "benchmark"
    if family == "player_stats":
        return "legacy"
    if family in ("players", "players_components"):
        return "identity"
    if family == "misc" or family not in CORE_FAMILIES:
        return "reference"
    return "statistics"


def build_catalog(
    releases: list[dict[str, Any]],
    opportunity: list[dict[str, Any]],
    directory: list[dict[str, Any]],
    *,
    observed_at: datetime,
) -> Catalog:
    require_aware(observed_at)
    assets = []
    for repo, items in ((CORE_REPO, releases), (OPPORTUNITY_REPO, opportunity)):
        for release in items:
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = release["tag_name"]
            if repo == OPPORTUNITY_REPO and not tag.endswith("-data"):
                continue
            _parts(tag)
            names = set()
            for entry in release["assets"]:
                name = entry["name"]
                stem, ext = _parts(name)
                if name in names:
                    raise ValueError("DUPLICATE_ASSET")
                names.add(name)
                expected = f"https://github.com/{repo}/releases/download/{tag}/{quote(name)}"
                if unquote(entry["browser_download_url"]) != unquote(expected):
                    raise ValueError("SOURCE_SCOPE_MISMATCH")
                family = tag if repo == CORE_REPO else "ff_opportunity"
                usage = _usage(family, stem)
                license = (
                    "CC-BY-SA-4.0"
                    if family == "ftn_charting" or family == "pbp_participation"
                    else "CC-BY-4.0"
                    if repo == CORE_REPO
                    else "source-specific; see upstream ffopportunity terms"
                )
                digest = entry.get("digest")
                assets.append(
                    Asset(
                        source_id=f"{repo}:{entry['id']}",
                        repository=repo,
                        release=tag,
                        family=family,
                        logical_key=f"{repo}/{tag}/{stem}",
                        filename=name,
                        format=ext,
                        source_url=expected,
                        size=entry["size"],
                        source_updated_at=entry.get("updated_at"),
                        source_created_at=entry.get("created_at"),
                        provider_sha256=digest.removeprefix("sha256:") if digest else None,
                        selected=False,
                        disposition="candidate"
                        if entry.get("state", "uploaded") == "uploaded"
                        else "unavailable",
                        usage=usage,
                        license=license,
                        attribution="FTN Data via nflverse"
                        if family in ("ftn_charting", "pbp_participation")
                        else "nflverse and original source authors"
                        if repo == CORE_REPO
                        else "ffopportunity / ffverse; benchmark only",
                        availability_note="From 2023 FTN participation is postseason-only; never infer in-season availability."
                        if family == "pbp_participation"
                        else "From 2025 depth charts are timestamped observations, not fictional weekly releases."
                        if family == "depth_charts"
                        else "Asset timestamps describe this file revision, not historical row publication time.",
                    )
                )
    for entry in directory:
        if entry.get("type", "file") != "file":
            continue
        name = entry["name"]
        stem, ext = _parts(name)
        url = entry["download_url"]
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname != "raw.githubusercontent.com"
            or parts.query
            or not parts.path.startswith("/dynastyprocess/data/")
            or not parts.path.endswith("/files/" + name)
        ):
            raise ValueError("SOURCE_SCOPE_MISMATCH")
        assets.append(
            Asset(
                source_id="dynastyprocess/data:" + entry["sha"],
                repository="dynastyprocess/data",
                release="files",
                family="ff_playerids" if stem == "db_playerids" else "dynastyprocess",
                logical_key="dynastyprocess/data/files/" + stem,
                filename=name,
                format=ext,
                source_url=url,
                size=entry["size"],
                source_created_at=None,
                source_updated_at=None,
                git_blob_sha1=entry["sha"],
                selected=False,
                disposition="candidate",
                usage="identity" if stem == "db_playerids" else "benchmark",
                license="source-specific; DynastyProcess/FantasyPros terms",
                attribution="DynastyProcess / FantasyPros via ffverse",
                availability_note="Benchmark/reference only except explicit ID crosswalks; no FFA scoring substitution.",
            )
        )
    best: dict[str, Asset] = {}
    rank = {ext: i for i, ext in enumerate(EXTENSIONS)}
    for asset in assets:
        if asset.disposition == "unavailable":
            continue
        current = best.get(asset.logical_key)
        if current is None or rank.get(asset.format, 99) < rank.get(current.format, 99):
            best[asset.logical_key] = asset
    resolved = tuple(
        a.model_copy(
            update={
                "selected": best.get(a.logical_key) == a,
                "disposition": "selected"
                if best.get(a.logical_key) == a
                else a.disposition
                if a.disposition == "unavailable"
                else "format_mirror",
            }
        )
        for a in assets
    )
    return Catalog(
        observed_at=observed_at,
        assets=resolved,
        sources=tuple(sorted({a.repository for a in assets})),
    )
