"""Full release discovery selects every logical variant, with explicit usage and mirrors."""

from datetime import UTC, datetime

import pytest
from arbit_data.nflverse.catalog import build_catalog


def release(tag, names, repo="nflverse/nflverse-data"):
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "id": i + 1,
                "name": name,
                "state": "uploaded",
                "size": 10,
                "created_at": "2026-10-30T00:00:00Z",
                "updated_at": "2026-10-31T00:00:00Z",
                "digest": None,
                "browser_download_url": f"https://github.com/{repo}/releases/download/{tag}/{name}",
            }
            for i, name in enumerate(names)
        ],
    }


def test_catalog_keeps_all_seasons_subtypes_and_orphan_serializations():
    releases = [
        release(
            "stats_player",
            [
                "stats_player_week_2026.csv",
                "stats_player_week_2026.parquet",
                "stats_player_reg_1999.parquet",
                "timestamp.json",
                "timestamp.txt",
            ],
        ),
        release("pfr_advstats", ["advstats_season_pass_2026.rds"]),
        release("misc", ["patch.csv"]),
        release("test", ["combines.csv"]),
    ]
    result = build_catalog(releases, [], [], observed_at=datetime.now(UTC))
    chosen = [a for a in result.assets if a.selected]
    assert len(chosen) == 6
    assert any(a.filename == "stats_player_reg_1999.parquet" for a in chosen)
    assert next(a for a in chosen if a.filename.endswith(".rds")).format == "rds"
    assert next(a for a in chosen if a.family == "test").usage == "diagnostic"
    assert next(a for a in chosen if a.filename == "timestamp.json").usage == "metadata"
    assert len(result.assets) == 8
    assert sum(a.disposition == "format_mirror" for a in result.assets) == 2


def test_ftn_and_ffverse_licenses_usage_are_not_collapsed():
    result = build_catalog(
        [
            release("ftn_charting", ["ftn_charting_2026.parquet"]),
            release("pbp_participation", ["pbp_participation_2025.parquet"]),
        ],
        [release("latest-data", ["ep_weekly_2026.parquet"], repo="ffverse/ffopportunity")],
        [],
        observed_at=datetime.now(UTC),
    )
    assert result.assets[0].license == "CC-BY-SA-4.0"
    assert next(a for a in result.assets if a.family == "ff_opportunity").usage == "benchmark"
    assert (
        "postseason"
        in next(a for a in result.assets if a.family == "pbp_participation").availability_note
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["assets"][0].update(browser_download_url="https://evil.invalid/data.parquet"),
        lambda r: r["assets"][0].update(name="../escape.parquet"),
        lambda r: r["assets"][0].update(size=-1),
    ],
)
def test_untrusted_catalog_fields_fail_closed(change):
    item = release("players", ["players.parquet"])
    change(item)
    with pytest.raises(ValueError):
        build_catalog([item], [], [], observed_at=datetime.now(UTC))


def test_model_artifacts_are_recorded_separately_and_ngs_attribution_is_historical():
    result = build_catalog(
        [release("pbp_participation", ["pbp_participation_2016.parquet"])],
        [release("latest-model", ["model.zip"], repo="ffverse/ffopportunity")],
        [],
        observed_at=datetime.now(UTC),
    )
    assert result.assets[0].license == "CC-BY-4.0"
    assert "NGS" in result.assets[0].attribution
    assert result.excluded[0]["reason"] == "model_artifact_not_dataset"
