"""Coverage results exercise every audited request and retain safe failure evidence."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arbit_data.espn.client import EndpointResponse
from arbit_data.espn.endpoints import Endpoint, build_request
from arbit_data.espn.transport import EspnError, SourceReceipt
from arbit_data.espn.verification import verify_audit

AUDIT = Path(__file__).resolve().parents[3] / "docs/research/espn-public-2026-10-30.json"


def records():
    return json.loads(AUDIT.read_bytes())["requests"]


class SourceClient:
    def __init__(self, error=None):
        self.error = error

    def fetch(self, endpoint, options):
        if self.error:
            raise self.error
        request = build_request(endpoint, options)
        capability = "available"
        missing = ()
        if endpoint == Endpoint.LEAGUE:
            if options.views == ("mStandings",):
                capability = "limited"
                missing = ("teams.*.record",)
            elif options.views == ("mSchedule",):
                capability = "limited"
                missing = ("schedule",)
            elif options.views == ("proTeamSchedules_wl",):
                capability = "limited"
                missing = ("proTeamSchedules",)
            elif options.views in [("modular",), ("mNav",)]:
                capability = "metadata_only"
        return EndpointResponse(
            endpoint,
            {"PRIVATE NAME": "PRIVATE ARTICLE TEXT"},
            SourceReceipt(
                request.url,
                datetime(2026, 10, 31, tzinfo=UTC),
                "a" * 64,
                100,
                request.fantasy_filter,
            ),
            capability,
            missing,
        )


def test_full_live_report_verifies_every_callable_case_and_no_payload_leaks():
    report = verify_audit(records(), SourceClient(), live=True)
    assert report["success"] is True and report["liveVerificationPassed"] is True
    assert (
        report["auditCases"] == 81
        and report["callableCases"] == 68
        and report["excludedCases"] == 13
    )
    assert (
        report["attemptedCases"] == 68
        and report["passedCases"] == 68
        and report["failedCases"] == 0
    )
    assert report["capabilities"] == {"available": 63, "limited": 3, "metadata_only": 2}
    assert report["endpointFamilies"] == 19
    assert len(report["cases"]) == 81
    output = json.dumps(report)
    assert "PRIVATE NAME" not in output and "PRIVATE ARTICLE" not in output
    transactions = [row for row in report["cases"] if row["case"] == "transactions-period-1"][0]
    assert "scoringPeriodId=1" in transactions["source"]["url"]
    assert transactions["source"]["sha256"] == "a" * 64


def test_catalog_mode_makes_no_source_claim():
    report = verify_audit(records())
    assert report["success"] is True and report["wiringComplete"] is True
    assert report["liveVerificationPassed"] is None
    assert report["attemptedCases"] == 0 and report["passedCases"] == 0
    assert report["capabilities"] == {}
    assert all("source" not in row for row in report["cases"])


@pytest.mark.parametrize(
    "error",
    [
        EspnError("ACCESS_DENIED", status=401),
        EspnError("RATE_LIMITED", status=429, retry_after_seconds=120),
    ],
)
def test_access_or_rate_failure_stops_without_losing_partial_report(error):
    report = verify_audit(records(), SourceClient(error), live=True)
    assert report["success"] is False and report["liveVerificationPassed"] is False
    assert report["attemptedCases"] == 1 and report["failedCases"] == 1
    assert report["notAttemptedCases"] == 67
    assert report["stoppedReason"] == error.code
    first = report["cases"][0]
    assert first["error"]["code"] == error.code
    assert first["error"]["retryAfterSeconds"] == error.retry_after_seconds
    assert len(report["cases"]) == 81


def test_missing_useful_data_is_failed_coverage_even_when_http_succeeded():
    class Missing(SourceClient):
        def fetch(self, endpoint, options):
            result = super().fetch(endpoint, options)
            return EndpointResponse(
                endpoint, result.payload, result.receipt, "limited", ("settings",)
            )

    report = verify_audit(records(), Missing(), live=True)
    assert report["success"] is False
    assert report["failedCases"] > 0
    assert report["cases"][0]["error"]["code"] == "CAPABILITY_CHANGED"
    assert "source" in report["cases"][0]


def test_new_unregistered_success_fails_before_source_use():
    data = records()
    data.append(
        {
            "case": "unregistered",
            "method": "GET",
            "status": 200,
            "outcome": "data_returned",
            "url": "https://site.api.espn.com/unregistered",
            "requestHeaders": {},
        }
    )
    with pytest.raises(ValueError):
        verify_audit(data, SourceClient(), live=True)


def test_invalid_audit_outcome_is_rejected_before_network():
    class Forbidden:
        def fetch(self, *args):
            raise AssertionError("Invalid audit reached the source")

    data = records()
    data[-1]["outcome"] = "unknown-outcome"
    with pytest.raises(ValueError):
        verify_audit(data, Forbidden(), live=True)


def test_empty_audit_cannot_claim_complete_wiring():
    with pytest.raises(ValueError):
        verify_audit([])
