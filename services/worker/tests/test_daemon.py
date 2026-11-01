import threading
from datetime import UTC, datetime, timedelta

from arbit_worker.daemon import StatisticsLane, run_lane
from sqlalchemy.exc import OperationalError


class ExplodingLane:
    name = "test"

    def __init__(self, stop: threading.Event):
        self.calls, self.stop = 0, stop

    def step(self) -> float:
        self.calls += 1
        if self.calls == 1:
            raise OperationalError("SELECT", {}, Exception("secret-host"))
        if self.calls == 2:
            raise RuntimeError("provider said /private/path/token=abc")
        self.stop.set()
        return 0.0


def test_lane_survives_failures_and_logs_only_safe_codes(capsys, monkeypatch):
    stop = threading.Event()
    lane = ExplodingLane(stop)
    monkeypatch.setattr(threading.Event, "wait", lambda self, timeout=None: None)
    run_lane(lane, stop)
    output = capsys.readouterr().out
    assert lane.calls == 3, "two failures must not stop the lane"
    assert "DATABASE_UNAVAILABLE" in output and "LANE_ERROR" in output
    assert "secret-host" not in output and "token=abc" not in output


class Health:
    """Records health calls through the real functions' signatures."""

    def __init__(self, monkeypatch, last):
        from arbit_data import freshness

        self.success, self.failures = [], []
        monkeypatch.setattr(freshness, "last_success_of", lambda _u, _s: last)
        monkeypatch.setattr(freshness, "record_success", lambda *a, **k: self.success.append(k))
        monkeypatch.setattr(freshness, "record_failure", lambda *a, **k: self.failures.append(a[2]))


NOW = datetime(2026, 11, 1, tzinfo=UTC)


def test_statistics_runs_only_when_due_and_imports_the_discovered_catalog(monkeypatch):
    Health(monkeypatch, NOW - timedelta(hours=1))
    calls = []
    lane = StatisticsLane(None, run=lambda a: calls.append(a) or (0, ""), clock=lambda: NOW)
    lane.step()
    assert calls == [], "a fresh import is not repeated"

    health = Health(monkeypatch, NOW - timedelta(hours=25))
    outputs = iter([(0, '{"catalog_hash": "abc"}'), (0, "{}")])
    calls = []

    def run(arguments):
        calls.append(arguments)
        return next(outputs)

    StatisticsLane(None, run=run, clock=lambda: NOW).step()
    assert calls == [
        ["nflverse-catalog", "--live"],
        ["nflverse-import", "--catalog", "abc", "--workers", "2"],
    ]
    assert health.success and not health.failures


def test_statistics_failure_is_recorded_and_waits_before_retrying(monkeypatch):
    health = Health(monkeypatch, NOW - timedelta(days=3))
    calls = []
    lane = StatisticsLane(None, run=lambda a: calls.append(a) or (1, ""), clock=lambda: NOW)
    lane.step()
    assert health.failures == ["CATALOG_FAILED"]
    lane.step()
    assert len(calls) == 1, "a failed import must not retry in a tight loop"


def test_statistics_rejects_unparseable_catalog_output(monkeypatch):
    health = Health(monkeypatch, NOW - timedelta(days=3))
    StatisticsLane(None, run=lambda a: (0, "not json"), clock=lambda: NOW).step()
    assert health.failures == ["IMPORT_FAILED"]
