"""Durable scheduler and recovery exercise real transactions with a scripted source."""

from datetime import timedelta

import pytest
from arbit_data.archives import CaptureArchive
from arbit_data.espn.transport import EspnError
from arbit_data.jobs import JobQueue
from arbit_data.league_store import read_current, read_sync
from arbit_data.sync import SyncService, schedule_sync
from sqlalchemy import text

pytestmark = pytest.mark.integration


class Source:
    def __init__(self, captured):
        self.captured = captured
        self.calls = 0
        self.audits = 0
        self.error = None

    def acquire(self, season):
        self.calls += 1
        if self.error:
            raise self.error
        return self.captured.acquisition

    def audit(self, season):
        self.audits += 1
        return self.captured.verification


def test_scheduler_deduplicates_and_success_reuses_verified_rules(uow, tmp_path, captured_input):
    from test_canonical_publication import later

    now = captured_input.acquisition.capture_finished_at
    one = schedule_sync(uow, 2026, now=now)
    assert schedule_sync(uow, 2026, now=now) == one
    source = Source(captured_input)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    result = service.run_one()
    assert result["status"] == "succeeded" and result["changed"] is True
    assert source.audits == 1
    assert schedule_sync(uow, 2026, now=now + timedelta(seconds=299)) is None
    source.captured = later(captured_input, seconds=300)
    service.clock = lambda: now + timedelta(seconds=300)
    schedule_sync(uow, 2026, now=service.clock())
    result = service.run_one()
    assert result["changed"] is False and source.audits == 1
    assert read_sync(uow, 2026, now=service.clock())["status"] == "fresh"


def test_failure_preserves_snapshot_and_retry_after_survives_new_service(
    uow, tmp_path, captured_input
):
    from test_canonical_publication import later

    start = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    service = SyncService(
        uow, CaptureArchive(tmp_path), source, clock=lambda: start, jitter=lambda: 0
    )
    schedule_sync(uow, 2026, now=start)
    first = service.run_one()
    now = start + timedelta(seconds=300)
    schedule_sync(uow, 2026, now=now)
    source.error = EspnError("RATE_LIMITED", status=429, retry_after_seconds=120)
    service.clock = lambda: now
    failure = service.run_one()
    assert failure["status"] == "retrying" and failure["error_code"] == "RATE_LIMITED"
    assert read_current(uow, 2026, now=now)["snapshot_id"] == first["snapshot_id"]
    assert read_sync(uow, 2026, now=now)["status"] == "degraded"
    restarted = SyncService(
        uow, CaptureArchive(tmp_path), source, clock=lambda: now + timedelta(seconds=119)
    )
    assert restarted.run_one() is None
    source.error = None
    source.captured = later(captured_input, seconds=420)
    restarted.clock = lambda: now + timedelta(seconds=120)
    assert restarted.run_one()["status"] == "succeeded"


def test_auth_or_rules_failure_pauses_automatic_work_but_manual_resume_is_explicit(
    uow, tmp_path, captured_input
):
    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    source.error = EspnError("ACCESS_DENIED", status=403)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    schedule_sync(uow, 2026, now=now)
    assert service.run_one()["status"] == "paused"
    assert read_sync(uow, 2026, now=now)["paused"] is True
    assert schedule_sync(uow, 2026, now=now + timedelta(days=1)) is None
    assert schedule_sync(uow, 2026, now=now + timedelta(days=1), force=True) is not None


def test_incomplete_new_rules_are_quarantined_and_last_good_is_retained(
    uow, tmp_path, captured_input
):
    from test_canonical_publication import later

    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    schedule_sync(uow, 2026, now=now)
    first = service.run_one()
    source.captured = later(
        captured_input,
        seconds=300,
        change=lambda d: d["settings"]["scoringSettings"]["scoringItems"][0].update(points="-3"),
    )
    source.captured = source.captured.model_copy(
        update={"verification": {"success": False, "issues": [{"code": "PLAYER_TOTAL_MISMATCH"}]}}
    )
    service.clock = lambda: now + timedelta(seconds=300)
    schedule_sync(uow, 2026, now=service.clock())
    result = service.run_one()
    assert result["status"] == "paused"
    assert read_current(uow, 2026, now=service.clock())["snapshot_id"] == first["snapshot_id"]
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM source_capture WHERE status='quarantined'")) == 1


def test_replay_is_offline_and_never_claims_new_freshness(uow, tmp_path, captured_input):
    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    schedule_sync(uow, 2026, now=now)
    result = service.run_one()
    digest = result["manifest_hash"]
    source.error = AssertionError("Replay must never call ESPN")
    service.clock = lambda: now + timedelta(days=2)
    replay = service.replay(digest)
    assert replay.replayed and str(replay.snapshot_id) == result["snapshot_id"]
    assert read_sync(uow, 2026, now=service.clock())["stale"] is True


def test_expired_worker_cannot_change_health_or_publish_after_replacement(
    uow, tmp_path, captured_input
):
    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    schedule_sync(uow, 2026, now=now)

    def lose_lease(season):
        service.clock = lambda: now + timedelta(seconds=121)
        replacement = service.queue.claim_job("replacement", service.clock(), job_type="espn.sync")
        assert replacement is not None
        return captured_input.acquisition

    source.acquire = lose_lease
    assert service.run_one()["status"] == "lease_lost"
    assert read_current(uow, 2026, now=service.clock()) is None
    assert read_sync(uow, 2026, now=service.clock())["consecutive_failures"] == 0


def test_retry_exhaustion_waits_before_starting_a_new_job(uow, tmp_path, captured_input):
    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    source.error = EspnError("NETWORK_ERROR")
    service = SyncService(
        uow, CaptureArchive(tmp_path), source, clock=lambda: now, jitter=lambda: 0
    )
    schedule_sync(uow, 2026, now=now)
    for attempt, delay in enumerate((5, 10, 20, 40, 900), 1):
        result = service.run_one()
        assert result["status"] == ("retrying" if attempt < 5 else "exhausted")
        now += timedelta(seconds=delay)
    assert schedule_sync(uow, 2026, now=now - timedelta(seconds=1)) is None
    assert schedule_sync(uow, 2026, now=now) is not None


def test_job_type_filter_does_not_claim_unrelated_work(uow, tmp_path, captured_input):
    now = captured_input.acquisition.capture_finished_at
    other = JobQueue(uow).enqueue("fixture", "fixture://x", "unrelated", now)
    service = SyncService(uow, CaptureArchive(tmp_path), Source(captured_input), clock=lambda: now)
    assert service.run_one() is None
    assert JobQueue(uow).get_job(other.id).status == "queued"


def test_heartbeat_keeps_slow_acquisition_leased(uow, tmp_path, captured_input):
    import threading

    from arbit_data.schema import job
    from sqlalchemy import select

    now = captured_input.acquisition.capture_finished_at
    current = [now]
    source = Source(captured_input)
    service = SyncService(
        uow, CaptureArchive(tmp_path), source, clock=lambda: current[0], heartbeat_seconds=0.01
    )
    schedule_sync(uow, 2026, now=now)

    def slow_acquire(season):
        current[0] = now + timedelta(seconds=100)
        deadline = __import__("time").monotonic() + 3
        while __import__("time").monotonic() < deadline:
            with uow.engine.connect() as c:
                expires = c.scalar(select(job.c.lease_until).where(job.c.status == "running"))
            if expires > now + timedelta(seconds=200):
                current[0] = now + timedelta(seconds=130)
                return captured_input.acquisition
            threading.Event().wait(0.005)
        pytest.fail("heartbeat did not extend source work lease")

    source.acquire = slow_acquire
    assert service.run_one()["status"] == "succeeded"


def test_unsupported_rule_capture_is_quarantined_for_inspection(uow, tmp_path, captured_input):
    from test_canonical_publication import later

    bad = later(
        captured_input,
        seconds=0,
        change=lambda d: d["settings"]["scoringSettings"]["scoringItems"][0].update(statId=9999),
        verification="keep",
    )
    now = bad.acquisition.capture_finished_at
    service = SyncService(uow, CaptureArchive(tmp_path), Source(bad), clock=lambda: now)
    schedule_sync(uow, 2026, now=now)
    assert service.run_one()["status"] == "paused"
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM source_capture WHERE status='quarantined'")) == 1


def test_crashed_last_attempt_enters_recovery_delay(uow, tmp_path, captured_input):
    from arbit_data.schema import job
    from sqlalchemy import update

    now = captured_input.acquisition.capture_finished_at
    schedule_sync(uow, 2026, now=now)
    q = JobQueue(uow, lease_seconds=10)
    lease = q.claim_job("crashed", now, job_type="espn.sync")
    with uow.engine.begin() as c:
        c.execute(update(job).where(job.c.id == lease.id).values(attempts=5))
    service = SyncService(
        uow,
        CaptureArchive(tmp_path),
        Source(captured_input),
        clock=lambda: now + timedelta(seconds=11),
    )
    assert service.run_one() is None
    assert read_sync(uow, 2026, now=service.clock())["error_code"] == "LEASE_EXHAUSTED"
    assert schedule_sync(uow, 2026, now=service.clock()) is None
    assert schedule_sync(uow, 2026, now=service.clock() + timedelta(seconds=900)) is not None


def test_extreme_actual_points_quarantine_safely_and_worker_can_continue(
    uow, tmp_path, captured_input
):
    from test_canonical_publication import later

    now = captured_input.acquisition.capture_finished_at
    source = Source(captured_input)
    service = SyncService(uow, CaptureArchive(tmp_path), source, clock=lambda: now)
    schedule_sync(uow, 2026, now=now)
    first = service.run_one()

    def extreme(d):
        d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]["stats"] = [
            {
                "seasonId": 2026,
                "scoringPeriodId": 8,
                "statSourceId": 0,
                "statSplitTypeId": 1,
                "appliedTotal": "1e1000",
            }
        ]

    source.captured = later(captured_input, seconds=300, change=extreme)
    service.clock = lambda: now + timedelta(seconds=300)
    schedule_sync(uow, 2026, now=service.clock())
    failure = service.run_one()
    assert failure["status"] == "paused" and failure["error_code"] == "INVALID_ACTUAL_POINTS"
    assert read_current(uow, 2026, now=service.clock())["snapshot_id"] == first["snapshot_id"]
    with uow.engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM source_capture WHERE status='quarantined'")) == 1
    source.captured = later(captured_input, seconds=600)
    service.clock = lambda: now + timedelta(seconds=600)
    schedule_sync(uow, 2026, now=service.clock(), force=True)
    assert service.run_one()["status"] == "succeeded"
