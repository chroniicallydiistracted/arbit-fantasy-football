from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.integration


def test_expired_lease_is_reclaimed_and_stale_completion_is_fenced(uow):
    from arbit_data.jobs import JobQueue, LeaseLostError

    queue = JobQueue(uow, lease_seconds=30, max_attempts=2)
    now = datetime.now(UTC)
    job = queue.enqueue("fixture", "fixture://one", "one", now)
    first = queue.claim_job("worker-1", now)
    second = queue.claim_job("worker-2", now + timedelta(seconds=31))
    assert first.id == second.id == job.id
    assert first.lease_token != second.lease_token
    with pytest.raises(LeaseLostError):
        queue.complete_job(job.id, first.lease_token, "result://stale", now + timedelta(seconds=32))
    queue.complete_job(job.id, second.lease_token, "result://valid", now + timedelta(seconds=32))
    assert queue.get_job(job.id).result_ref == "result://valid"
    assert queue.claim_job("worker-3", now + timedelta(seconds=80)) is None


def test_two_workers_claim_distinct_work_and_enqueue_is_idempotent(uow):
    from arbit_data.jobs import JobQueue

    queue = JobQueue(uow)
    now = datetime.now(UTC)
    first = queue.enqueue("fixture", "fixture://one", "one", now)
    assert queue.enqueue("fixture", "fixture://one", "one", now) == first
    queue.enqueue("fixture", "fixture://two", "two", now)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda worker: queue.claim_job(worker, now), ["a", "b"]))
    assert claims[0].id != claims[1].id


def test_retries_are_delayed_and_exhaustion_is_persisted(uow):
    from arbit_data.jobs import JobQueue

    queue = JobQueue(uow, max_attempts=2)
    now = datetime.now(UTC)
    job = queue.enqueue("fixture", "fixture://one", "one", now)
    lease = queue.claim_job("worker", now)
    queue.fail_job(job.id, lease.lease_token, "UPSTREAM_UNAVAILABLE", now)
    assert queue.claim_job("worker", now + timedelta(seconds=4)) is None
    lease = queue.claim_job("worker", now + timedelta(seconds=5))
    queue.fail_job(job.id, lease.lease_token, "UPSTREAM_UNAVAILABLE", now + timedelta(seconds=5))
    assert queue.get_job(job.id).status == "failed"
    assert queue.claim_job("worker", now + timedelta(hours=1)) is None


def test_expired_final_attempt_and_conflicting_idempotency_are_visible(uow):
    from arbit_data.jobs import IdempotencyConflictError, JobQueue

    queue = JobQueue(uow, lease_seconds=10, max_attempts=1)
    now = datetime.now(UTC)
    job = queue.enqueue("fixture", "fixture://one", "one", now)
    with pytest.raises(IdempotencyConflictError):
        queue.enqueue("fixture", "fixture://different", "one", now)
    queue.claim_job("worker", now)
    assert queue.claim_job("recovery", now + timedelta(seconds=11)) is None
    assert queue.get_job(job.id).status == "failed"


def test_heartbeat_extends_live_lease_but_cannot_revive_expired_lease(uow):
    from arbit_data.jobs import JobQueue, LeaseLostError

    queue = JobQueue(uow, lease_seconds=10)
    now = datetime.now(UTC)
    job = queue.enqueue("fixture", "fixture://one", "one", now)
    lease = queue.claim_job("worker", now)
    assert queue.heartbeat(
        job.id, lease.lease_token, now + timedelta(seconds=8)
    ) == now + timedelta(seconds=18)
    assert queue.claim_job("other", now + timedelta(seconds=11)) is None
    with pytest.raises(LeaseLostError):
        queue.heartbeat(job.id, lease.lease_token, now + timedelta(seconds=19))
