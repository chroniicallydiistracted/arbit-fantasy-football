"""Safe audit-to-adapter coverage, with opt-in serial live verification."""

from collections import Counter
from typing import Any, Protocol

from arbit_data.espn.audit_requests import audit_requests
from arbit_data.espn.client import EndpointResponse
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.transport import EspnError, utc_now


class SourceClient(Protocol):
    def fetch(self, endpoint: Endpoint, options: EndpointOptions) -> EndpointResponse: ...


def _counts(payload: dict[str, Any] | list[Any] | bytes) -> dict[str, int]:
    if isinstance(payload, list):
        return {"records": len(payload)}
    if isinstance(payload, bytes):
        return {"bytes": len(payload)}
    result = {}
    for path in [
        "players",
        "teams",
        "members",
        "schedule",
        "transactions",
        "draftDetail.picks",
        "settings.scoringSettings.scoringItems",
        "settings.proTeams",
        "news.feed",
        "events",
        "articles",
        "children",
        "headlines",
        "items",
        "drives.previous",
        "scoringPlays",
    ]:
        value: Any = payload
        for key in path.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, list):
            result[path] = len(value)
    return result


def verify_audit(
    records: list[dict[str, Any]], client: SourceClient | None = None, *, live: bool = False
) -> dict[str, Any]:
    audited = audit_requests(records)  # Classify everything before any network action.
    if live and client is None:
        raise ValueError("Live verification requires a source client")
    started = utc_now()
    rows: list[dict[str, Any]] = []
    capabilities: Counter[str] = Counter()
    attempted = passed = failed = 0
    stopped: str | None = None
    for audited_request in audited:
        row: dict[str, Any] = {
            "case": audited_request.case,
            "expectedOutcome": audited_request.expected,
        }
        request = audited_request.request
        if request is None:
            row.update(state="excluded", reason=audited_request.excluded)
        else:
            row.update(endpoint=request.endpoint.value, state="not_attempted" if live else "wired")
            if live and stopped is None:
                attempted += 1
                try:
                    assert client is not None
                    response = client.fetch(request.endpoint, request.options)
                    row.update(
                        capability=response.capability,
                        missingSections=list(response.missing_sections),
                        counts=_counts(response.payload),
                    )
                    receipt = response.receipt
                    row["source"] = {
                        "url": receipt.url,
                        "fantasyFilter": receipt.fantasy_filter,
                        "observedAt": receipt.observed_at.isoformat(),
                        "sha256": receipt.sha256,
                        "bytes": receipt.byte_count,
                    }
                    expected = {
                        "data_returned": "available",
                        "asset_returned": "available",
                        "missing_expected_data": "limited",
                        "json_metadata_only": "metadata_only",
                    }.get(audited_request.expected)
                    capabilities[response.capability] += 1
                    if expected is None:
                        raise ValueError("Unknown expected audit capability")
                    if response.capability == expected or response.capability == "available":
                        passed += 1
                        row["state"] = "passed"
                    else:
                        failed += 1
                        row.update(state="failed", error={"code": "CAPABILITY_CHANGED"})
                except EspnError as error:
                    failed += 1
                    row.update(
                        state="failed",
                        error={
                            "code": error.code,
                            "status": error.status,
                            "retryAfterSeconds": error.retry_after_seconds,
                        },
                    )
                    if error.code in {
                        "ACCESS_DENIED",
                        "RATE_LIMITED",
                        "UNAVAILABLE",
                        "NETWORK_ERROR",
                    }:
                        stopped = error.code
        rows.append(row)
    callable_count = sum(request.request is not None for request in audited)
    live_passed = None if not live else failed == 0 and attempted == callable_count
    return {
        "schemaVersion": 1,
        "mode": "live" if live else "catalog",
        "success": live_passed if live else True,
        "wiringComplete": True,
        "liveVerificationPassed": live_passed,
        "auditCases": len(audited),
        "callableCases": callable_count,
        "excludedCases": len(audited) - callable_count,
        "endpointFamilies": len(
            {row.request.endpoint for row in audited if row.request is not None}
        ),
        "attemptedCases": attempted,
        "passedCases": passed,
        "failedCases": failed,
        "notAttemptedCases": callable_count - attempted if live else callable_count,
        "capabilities": dict(capabilities),
        "stoppedReason": stopped,
        "startedAt": started.isoformat(),
        "finishedAt": utc_now().isoformat(),
        "cases": rows,
    }
