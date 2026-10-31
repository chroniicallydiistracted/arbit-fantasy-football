"""Atomic canonical truth, stable identities, replay, corrections and lease fencing."""

from dataclasses import replace
from datetime import timedelta

import pytest
from arbit_data.archives import CaptureArchive
from arbit_data.espn.contracts import League
from arbit_data.league_store import publish_capture, read_current, read_history
from arbit_data.snapshots import StaleSnapshotError
from sqlalchemy import text

pytestmark = pytest.mark.integration


def later(capture, seconds=60, change=None, verification="reuse"):
    data = capture.acquisition.league.model_dump(mode="json", by_alias=True)
    if change:
        change(data)
    old = capture.acquisition
    return capture.model_copy(
        update={
            "acquisition": replace(
                old,
                league=League.model_validate(data),
                receipts=tuple(
                    replace(r, observed_at=r.observed_at + timedelta(seconds=seconds))
                    for r in old.receipts
                ),
                capture_started_at=old.capture_started_at + timedelta(seconds=seconds),
                capture_finished_at=old.capture_finished_at + timedelta(seconds=seconds),
            ),
            "verification": None if verification == "reuse" else capture.verification,
        }
    )


def publish(uow, tmp_path, capture, **kwargs):
    digest = CaptureArchive(tmp_path).write(capture)
    return publish_capture(
        capture, digest, uow, now=capture.acquisition.capture_finished_at, **kwargs
    )


def count(uow, name):
    with uow.engine.connect() as c:
        return c.scalar(text(f"SELECT count(*) FROM {name}"))


def test_full_facts_and_exact_identities_survive_unchanged_refresh_and_replay(
    uow, tmp_path, captured_input
):
    one = publish(uow, tmp_path, captured_input)
    view = read_current(uow, 2026, now=captured_input.acquisition.capture_finished_at)
    assert view["snapshot_id"] == str(one.snapshot_id)
    doc = view["league"]
    assert len(doc["teams"]) == 2 and len(doc["players"]) == 3
    dst = next(p for p in doc["players"] if p["kind"] == "defense_unit")
    assert dst["id"] != dst["nfl_team_id"]
    assert (
        dst["official_current_points"] is None
    )  # A projection/appliedStatTotal is not actual points.
    assert doc["teams"][0]["points_for"] == "939.04"
    assert doc["recommendations_enabled"] is False
    aliases = count(uow, "entity_alias")
    two = publish(uow, tmp_path, later(captured_input))
    assert two.snapshot_id == one.snapshot_id and not two.changed
    assert count(uow, "league_snapshot") == count(uow, "outbox_event") == 1
    assert count(uow, "entity_alias") == aliases
    assert count(uow, "source_capture") == 2
    assert (
        read_current(
            uow, 2026, now=captured_input.acquisition.capture_finished_at + timedelta(seconds=61)
        )["sync"]["stale"]
        is False
    )
    assert publish(uow, tmp_path, captured_input).replayed
    assert count(uow, "league_snapshot") == 1


def test_changes_and_corrections_append_history_without_repromoting_old_capture(
    uow, tmp_path, captured_input
):
    first = publish(uow, tmp_path, captured_input)

    def correction(d):
        d["schedule"][0]["matchupPeriodId"] = 1

    second_input = later(captured_input, change=correction)
    second = publish(uow, tmp_path, second_input)
    third_input = later(
        second_input, change=lambda d: d["schedule"][0]["home"].update(totalPoints="101.25")
    )
    third = publish(uow, tmp_path, third_input)
    history = read_history(uow, 2026)
    assert len(history) == 3
    assert history[0]["kind"] == "correction"
    assert history[0]["previous_snapshot_id"] == str(second.snapshot_id)
    assert history[0]["changes"]["matchups"] == 1
    assert publish(uow, tmp_path, captured_input).snapshot_id == first.snapshot_id
    assert read_current(uow, 2026, now=third_input.acquisition.capture_finished_at)[
        "snapshot_id"
    ] == str(third.snapshot_id)
    with pytest.raises(StaleSnapshotError):
        publish(
            uow,
            tmp_path,
            later(
                captured_input,
                seconds=30,
                change=lambda d: d["teams"][0].update(name="Old late response"),
            ),
        )


def test_invalid_mapping_or_changed_unverified_rules_roll_back_every_write(
    uow, tmp_path, captured_input
):
    publish(uow, tmp_path, captured_input)
    aliases = count(uow, "entity_alias")
    invalid = later(
        captured_input, change=lambda d: d["teams"][0]["owners"].append("missing-member")
    )
    with pytest.raises(ValueError, match="UNRESOLVED_MANAGER"):
        publish(uow, tmp_path, invalid)
    changed = later(
        captured_input,
        change=lambda d: d["settings"]["scoringSettings"]["scoringItems"][0].update(points="-3"),
    )
    with pytest.raises(ValueError, match="SCORING_VERIFICATION_REQUIRED"):
        publish(uow, tmp_path, changed)
    assert count(uow, "entity_alias") == aliases
    assert count(uow, "league_snapshot") == count(uow, "source_capture") == 1


def test_leased_publication_completes_atomically_and_expired_worker_cannot_write(
    uow, tmp_path, captured_input
):
    from arbit_data.jobs import JobQueue, LeaseLostError

    q = JobQueue(uow, lease_seconds=60)
    now = captured_input.acquisition.capture_finished_at
    job = q.enqueue("espn.sync", "2026", "sync-one", now)
    lease = q.claim_job("one", now)
    result = publish(uow, tmp_path, captured_input, lease=lease)
    assert q.get_job(job.id).result_ref == str(result.snapshot_id)
    assert q.get_job(job.id).status == "succeeded"
    new = later(captured_input)
    q.enqueue("espn.sync", "2026", "sync-two", now)
    old = q.claim_job("old", now)
    q.claim_job("replacement", now + timedelta(seconds=61))
    with pytest.raises(LeaseLostError):
        publish(uow, tmp_path, new, lease=old)
    assert count(uow, "league_snapshot") == 1


def test_actual_points_use_exact_source_scope_and_affiliations_are_dated(
    uow, tmp_path, captured_input
):
    def actual(d):
        p = d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]
        p["stats"] = [
            {
                "seasonId": 2026,
                "scoringPeriodId": 8,
                "statSourceId": 0,
                "statSplitTypeId": 1,
                "appliedTotal": "12.34",
            },
            {
                "seasonId": 2026,
                "scoringPeriodId": 8,
                "statSourceId": 1,
                "statSplitTypeId": 1,
                "appliedTotal": "99",
            },
        ]

    one = later(captured_input, seconds=0, change=actual, verification="keep")
    publish(uow, tmp_path, one)
    doc = read_current(uow, 2026, now=one.acquisition.capture_finished_at)["league"]
    assert (
        next(p for p in doc["players"] if p["position"] == "QB")["official_current_points"]
        == "12.34"
    )
    changed = later(
        one,
        change=lambda d: d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"].update(
            proTeamId=2
        ),
    )
    publish(uow, tmp_path, changed)
    with uow.engine.connect() as c:
        rows = c.execute(
            text("SELECT valid_from,valid_to FROM team_affiliation ORDER BY valid_from")
        ).all()
    assert any(r.valid_to == changed.acquisition.capture_started_at for r in rows)


def test_aliases_and_documents_are_transactional_under_concurrent_publication(
    uow, tmp_path, captured_input
):
    from concurrent.futures import ThreadPoolExecutor

    digest = CaptureArchive(tmp_path).write(captured_input)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: publish_capture(
                    captured_input, digest, uow, now=captured_input.acquisition.capture_finished_at
                ),
                range(2),
            )
        )
    assert results[0].snapshot_id == results[1].snapshot_id
    assert count(uow, "outbox_event") == 1
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM canonical_entity")) == c.scalar(
            text("SELECT count(*) FROM entity_alias")
        )


def test_late_failure_rolls_back_identities_rules_and_publication(uow, tmp_path, captured_input):
    bad = later(
        captured_input,
        seconds=0,
        change=lambda d: d["schedule"][0].update(matchupPeriodId=99),
        verification="keep",
    )
    with pytest.raises(ValueError, match="UNKNOWN_MATCHUP_PERIOD_MAPPING"):
        publish(uow, tmp_path, bad)
    for name in (
        "canonical_entity",
        "entity_alias",
        "scoring_verification",
        "rule_version",
        "league_snapshot",
        "league_document",
        "source_capture",
        "outbox_event",
    ):
        assert count(uow, name) == 0


def test_new_rules_need_matching_lineup_context_and_leave_old_versions(
    uow, tmp_path, captured_input
):
    from arbit_data.espn.normalize import scoring_context

    publish(uow, tmp_path, captured_input)
    new = later(
        captured_input,
        change=lambda d: d["settings"]["scoringSettings"]["scoringItems"][0].update(points="-3"),
    )
    key, support = scoring_context(new.acquisition.league)
    report = {**captured_input.verification, "support": support, "lineupContextHash": key}
    new = new.model_copy(update={"verification": report})
    publish(uow, tmp_path, new)
    assert count(uow, "rule_version") == count(uow, "scoring_verification") == 2
    assert read_history(uow, 2026)[0]["changes"]["rules"] is True
    mismatch = later(
        new, change=lambda d: d["settings"]["rosterSettings"]["lineupSlotCounts"].update({"0": 2})
    )
    with pytest.raises(ValueError, match="SCORING_VERIFICATION_REQUIRED"):
        publish(uow, tmp_path, mismatch.model_copy(update={"verification": report}))
    assert count(uow, "rule_version") == 2


def test_last_confirmation_fences_older_response_and_replay_does_not_refresh(
    uow, tmp_path, captured_input
):
    publish(uow, tmp_path, captured_input)
    latest = later(captured_input, seconds=600)
    publish(uow, tmp_path, latest)
    with pytest.raises(StaleSnapshotError):
        publish(uow, tmp_path, later(captured_input, seconds=300))
    assert publish(uow, tmp_path, captured_input).replayed
    view = read_current(
        uow, 2026, now=latest.acquisition.capture_finished_at + timedelta(seconds=901)
    )
    assert view["sync"]["last_success_at"] == latest.acquisition.capture_started_at.isoformat()
    assert view["sync"]["stale"] is True


def test_expiring_during_transaction_rolls_back_publication(uow, tmp_path, captured_input):
    from arbit_data.jobs import JobQueue, LeaseLostError

    now = captured_input.acquisition.capture_finished_at
    queue = JobQueue(uow, lease_seconds=10)
    queue.enqueue("espn.sync", "2026", "expires", now)
    lease = queue.claim_job("slow", now)
    times = iter((now, now + timedelta(seconds=11)))
    digest = CaptureArchive(tmp_path).write(captured_input)
    with pytest.raises(LeaseLostError):
        publish_capture(captured_input, digest, uow, lease=lease, clock=lambda: next(times))
    assert count(uow, "league_snapshot") == count(uow, "entity_alias") == 0
