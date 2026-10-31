"""Cross-instance pacing, persisted circuit/cooldown, and released advisory locks."""

from datetime import UTC, datetime, timedelta

import pytest
from arbit_data.espn.gate import DatabaseGate
from arbit_data.espn.transport import EspnError

pytestmark = pytest.mark.integration


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 30, 12, tzinfo=UTC)

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += timedelta(seconds=seconds)


def test_instances_share_pacing_and_retry_after(uow):
    clock = Clock()
    first = DatabaseGate(uow, clock=clock, sleep=clock.sleep)
    second = DatabaseGate(uow, clock=clock, sleep=clock.sleep)
    with first.request():
        pass
    with second.request():
        assert clock.now == datetime(2026, 10, 30, 12, 0, 2, tzinfo=UTC)
    with pytest.raises(EspnError):
        with first.request():
            raise EspnError("RATE_LIMITED", status=429, retry_after_seconds=120)
    before = clock.now
    with pytest.raises(EspnError, match="SOURCE_COOLDOWN") as error:
        with second.request():
            pytest.fail("provider call during persisted cooldown")
    assert error.value.retry_after_seconds == 120
    assert clock.now == before
    clock.sleep(120)
    with second.request():
        pass


def test_transient_circuit_survives_new_instance_and_locks_release(uow):
    clock = Clock()
    for _ in range(3):
        with pytest.raises(EspnError, match="UNAVAILABLE"):
            with DatabaseGate(uow, clock=clock, sleep=clock.sleep).request():
                raise EspnError("UNAVAILABLE", status=503)
    with pytest.raises(EspnError, match="SOURCE_COOLDOWN"):
        with DatabaseGate(uow, clock=clock, sleep=clock.sleep).request():
            pass
    clock.sleep(60)
    with DatabaseGate(uow, clock=clock, sleep=clock.sleep).request():
        pass
