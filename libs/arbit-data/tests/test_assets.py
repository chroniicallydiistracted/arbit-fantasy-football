from datetime import UTC, datetime, timedelta

import pytest

T = datetime(2026, 10, 31, tzinfo=UTC)


def context(**overrides):
    from arbit_data.assets import AssetContext

    return AssetContext(
        kind="field",
        season=2026,
        season_type="regular",
        week=8,
        event_id="401873023",
        nfl_team_id="9",
        venue_id="3798",
        neutral_site=False,
        **overrides,
    )


def record():
    from arbit_data.assets import AssetRecord, Permission

    return AssetRecord(
        asset_id="synthetic-test-only",
        context=context(),
        variant="synthetic-test-variant",
        source_page="https://www.gridiron-uniforms.com/fields/controller/controller.php?action=view-year-all&year=2026",
        image_url="https://www.gridiron-uniforms.com/fields/images/synthetic-test-only.png",
        sha256="a" * 64,
        media_type="image/png",
        width=100,
        height=50,
        variant_verified=True,
        verified_at=T - timedelta(days=1),
        variant_evidence="synthetic-only-test-evidence",
        pattern_evidence="synthetic-only-test-pattern",
        attribution="Synthetic test attribution",
        permission=Permission(
            status="granted",
            kind="field",
            granted_at=T - timedelta(days=1),
            evidence="synthetic-only-test-grant",
            uses=("local_display", "local_cache"),
        ),
    )


def test_empty_manifest_and_unverified_context_fall_back():
    from arbit_data.assets import resolve_asset

    assert resolve_asset(context(), [], T)["status"] == "fallback"
    ctx = context().model_copy(update={"venue_id": None})
    assert resolve_asset(ctx, [record()], T)["status"] == "fallback"


def test_asset_metadata_requires_exact_game_week_team_venue_and_neutral_scope():
    from arbit_data.assets import resolve_asset

    for field, value in [
        ("event_id", "401873024"),
        ("week", 9),
        ("nfl_team_id", "29"),
        ("venue_id", "1"),
        ("neutral_site", True),
        ("season_type", "post"),
    ]:
        r = record()
        r = r.model_copy(update={"context": r.context.model_copy(update={field: value})})
        assert resolve_asset(context(), [r], T)["status"] == "fallback"


def test_grants_variant_evidence_and_observation_must_be_valid_at_cutoff():
    from arbit_data.assets import resolve_asset

    r = record()
    for changed in [
        r.model_copy(update={"variant_verified": False}),
        r.model_copy(update={"pattern_evidence": None}),
        r.model_copy(update={"verified_at": T + timedelta(days=1)}),
        r.model_copy(update={"permission": r.permission.model_copy(update={"status": "pending"})}),
        r.model_copy(update={"permission": r.permission.model_copy(update={"expires_at": T})}),
    ]:
        assert resolve_asset(context(), [changed], T)["status"] == "fallback"
    assert resolve_asset(context(), [r], T)["status"] == "eligible_metadata"
    assert resolve_asset(context(), [r], T)["local_asset_ready"] is False


def test_ambiguous_metadata_and_unsafe_sources_never_select_image():
    from arbit_data.assets import AssetRecord, resolve_asset

    r = record()
    assert (
        resolve_asset(context(), [r, r.model_copy(update={"asset_id": "second"})], T)["status"]
        == "fallback"
    )
    for url in [
        "https://evil.example/a.png",
        "https://user:secret@gridiron-uniforms.com/a.png",
        "http://gridiron-uniforms.com/a.png",
    ]:
        raw = r.model_dump()
        raw["image_url"] = url
        with pytest.raises(ValueError):
            AssetRecord.model_validate(raw)
