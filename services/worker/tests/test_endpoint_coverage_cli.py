"""The operator command reports real wiring and source failures separately."""

import json

import pytest
from arbit_data.espn.transport import EspnError
from arbit_worker import main as module


def test_catalog_command_has_no_network_or_live_success_claim(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("Catalog inspection must not open a transport")

    monkeypatch.setattr(module, "EspnTransport", forbidden)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-endpoints"])
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["callableCases"] == 68 and report["excludedCases"] == 13
    assert report["wiringComplete"] is True and report["liveVerificationPassed"] is None
    assert report["attemptedCases"] == 0


def test_live_failure_prints_safe_partial_report_and_exits_nonzero(monkeypatch, capsys):
    class Denied:
        def __init__(self, *args):
            pass

        def fetch(self, *args):
            raise EspnError("ACCESS_DENIED", status=401)

    monkeypatch.setattr(module, "EspnClient", Denied, raising=False)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-endpoints", "--live"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert caught.value.code == 1 and report["success"] is False
    assert report["attemptedCases"] == 1 and report["notAttemptedCases"] == 67
    assert report["cases"][0]["error"]["code"] == "ACCESS_DENIED"
    assert all("payload" not in row for row in report["cases"])


def test_invalid_audit_is_safe_failure_before_any_request(monkeypatch, capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    monkeypatch.setattr(
        "sys.argv", ["arbit-worker", "espn-endpoints", "--audit", str(bad), "--live"]
    )
    with pytest.raises(SystemExit) as caught:
        module.main()
    captured = capsys.readouterr()
    assert caught.value.code == 2
    assert json.loads(captured.err) == {"error": "AUDIT_INVALID"}
    assert str(bad) not in captured.err
