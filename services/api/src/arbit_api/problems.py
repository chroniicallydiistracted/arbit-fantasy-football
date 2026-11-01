"""Safe typed member errors and their executable OpenAPI media-type contract."""

import re
from http import HTTPStatus
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from arbit_api.member_contracts import Problem

PRIVATE_HEADERS = {
    "Cache-Control": "no-store, private",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Vary": "Cookie",
}
PROBLEM_STATUSES = (401, 403, 404, 409, 422, 429, 503)
SAFE_CODES = frozenset(
    {
        "AUTH_REQUIRED",
        "ADMIN_REQUIRED",
        "SNAPSHOT_NOT_FOUND",
        "SNAPSHOT_UNAVAILABLE",
        "BINDING_REQUIRED",
        "OIDC_NOT_CONFIGURED",
        "TEAM_CONTEXT_DENIED",
        "PERIOD_NOT_FOUND",
        "INVALID_SEARCH",
        "PLAYER_NOT_FOUND",
        "UNKNOWN_WATCHLIST_PLAYER",
        "UNKNOWN_MANAGER",
        "INVALID_INVITATION",
        "BOOTSTRAP_CLOSED",
        "INVITATION_LIMIT",
        "SIGN_IN_DENIED",
        "INVITATION_REQUIRED",
        "ACCOUNT_NOT_FOUND",
        "LAST_ADMINISTRATOR",
        "SIGN_IN_LIMIT",
        "SIGN_IN_FAILED",
        "INVALID_PREFERENCES",
        "PREFERENCES_CONFLICT",
        "BINDING_CONFLICT",
        "FIXTURE_LOOPBACK_ONLY",
        "ORIGIN_REQUIRED",
        "CSRF_REQUIRED",
        "MEMBER_STORAGE_UNAVAILABLE",
        "MEMBER_FACTS_UNAVAILABLE",
        "INVALID_REQUEST",
        "NOT_FOUND",
        "METHOD_NOT_ALLOWED",
        "REQUEST_FAILED",
    }
)
DETAILS = {
    "AUTH_REQUIRED": "Sign in to continue.",
    "BINDING_REQUIRED": "An administrator must approve your manager binding first.",
    "ADMIN_REQUIRED": "Administrator access is required.",
    "ORIGIN_REQUIRED": "The request origin could not be verified.",
    "CSRF_REQUIRED": "The request could not be verified.",
    "INVALID_REQUEST": "The request did not match the API contract.",
    "SIGN_IN_LIMIT": "Sign-in is temporarily busy. Try again later.",
    "LAST_ADMINISTRATOR": "At least one active administrator must remain.",
    "MEMBER_STORAGE_UNAVAILABLE": "Member storage is temporarily unavailable.",
    "MEMBER_FACTS_UNAVAILABLE": "Stored league facts are temporarily unavailable.",
}


def is_member_path(path: str) -> bool:
    return path.startswith("/auth/") or path.startswith("/api/")


def request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if not isinstance(existing, str) or re.fullmatch("[a-f0-9]{32}", existing) is None:
        existing = uuid4().hex
        request.state.request_id = existing
    return existing


def problem_response(
    request: Request, status: int, code: str, *, retry_after: int | None = None
) -> JSONResponse:
    # Codes are controlled server constants. Never return exception/provider/input messages.
    code = code if code in SAFE_CODES else "REQUEST_FAILED"
    identifier = request_id(request)
    problem = Problem(
        type=f"urn:arbit:problem:{code}",
        title=HTTPStatus(status).phrase,
        status=status,
        detail=DETAILS.get(code, "The request could not be completed."),
        instance=f"urn:arbit:request:{identifier}",
        code=code,
        requestId=identifier,
        error=code,
    )
    headers = {**PRIVATE_HEADERS, "X-Request-ID": identifier}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        problem.model_dump(mode="json"),
        status_code=status,
        media_type="application/problem+json",
        headers=headers,
    )


def problem_responses() -> dict[int | str, dict[str, Any]]:
    responses: dict[int | str, dict[str, Any]] = {}
    for status in PROBLEM_STATUSES:
        headers: dict[str, Any] = {
            "X-Request-ID": {
                "description": "Server-generated safe request correlation ID",
                "schema": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
            }
        }
        if status == 429:
            headers["Retry-After"] = {
                "description": "Seconds until retry",
                "schema": {"type": "integer", "minimum": 1},
            }
        responses[status] = {
            "model": Problem,
            "description": HTTPStatus(status).phrase,
            "headers": headers,
        }
    return responses


def install_problem_openapi(app: FastAPI) -> None:
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        schema = generate()
        # FastAPI registers typed additional-response schemas under JSON by default.
        # Keep its model registration and publish the actual RFC problem media type.
        for path, path_item in schema.get("paths", {}).items():
            if not is_member_path(path):
                continue
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                for response in operation.get("responses", {}).values():
                    content = response.get("content", {})
                    standard = content.get("application/json", {})
                    if standard.get("schema", {}).get("$ref") == "#/components/schemas/Problem":
                        content["application/problem+json"] = content.pop("application/json")
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
