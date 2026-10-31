"""Bounded public GitHub metadata and streamed data reads; signed redirect URLs stay private."""

import json
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from decimal import Decimal
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from arbit_data.errors import SourceError
from arbit_data.espn.gate import DatabaseGate
from arbit_data.espn.http_deadline import DeadlineHTTPSHandler
from arbit_data.espn.transport import _retry_after
from arbit_data.nflverse.catalog import Asset, Catalog, build_catalog
from arbit_data.nflverse.objects import ObjectRef, ObjectStore
from arbit_data.nflverse.provenance import requires_proof

REPOSITORIES = ("nflverse/nflverse-data", "ffverse/ffopportunity", "dynastyprocess/data")


def validate_url(url: str, *, redirect: bool = False) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or p.username or p.password or p.port not in (None, 443) or p.fragment:
        raise SourceError("SOURCE_SCOPE_MISMATCH")
    if redirect and p.hostname in (
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    ):
        return
    prefix = (
        "/repos/"
        if p.hostname == "api.github.com"
        else "/"
        if p.hostname in ("github.com", "raw.githubusercontent.com")
        else None
    )
    if (
        prefix is None
        or not any(p.path.startswith(prefix + repo + "/") for repo in REPOSITORIES)
        or p.query
        and p.hostname != "api.github.com"
    ):
        raise SourceError("SOURCE_SCOPE_MISMATCH")


class _Redirects(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Request | None:
        validate_url(newurl, redirect=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NflverseTransport:
    def __init__(self, gate: DatabaseGate | None = None, *, staged_downloads: bool = False):
        self.gate = gate
        self.staged_downloads = staged_downloads
        self.opener = build_opener(ProxyHandler({}), _Redirects(), DeadlineHTTPSHandler())

    @contextmanager
    def _response(self, url: str) -> Iterator[Any]:
        validate_url(url)
        try:
            with self.gate.request() if self.gate else nullcontext():
                request = Request(
                    url,
                    headers={
                        "Accept": "application/vnd.github+json"
                        if url.startswith("https://api.github.com/")
                        else "application/octet-stream",
                        "Accept-Encoding": "identity",
                        "User-Agent": "Arbit/0.1 nflverse read-only",
                    },
                )
                with self.opener.open(request, timeout=120) as response:
                    if (
                        response.status != 200
                        or response.headers.get("Content-Encoding", "identity") != "identity"
                    ):
                        raise SourceError("INVALID_RESPONSE")
                    if response.headers.get_content_type() == "text/html":
                        raise SourceError("INVALID_RESPONSE")
                    yield response
        except HTTPError as error:
            status = error.code
            retry = _retry_after(error.headers.get("Retry-After"))
            error.close()
            raise SourceError(
                "RATE_LIMITED"
                if status == 429 or status == 403 and retry
                else "ACCESS_DENIED"
                if status in (401, 403)
                else "NOT_FOUND"
                if status == 404
                else "UNAVAILABLE"
                if status >= 500
                else "HTTP_ERROR",
                status=status,
                retry_after_seconds=retry,
            ) from None
        except (URLError, OSError, HTTPException):
            raise SourceError("NETWORK_ERROR") from None

    def json(self, url: str) -> Any:
        with self._response(url) as response:
            data = response.read(16 * 1024 * 1024 + 1)
            if len(data) > 16 * 1024 * 1024:
                raise SourceError("METADATA_TOO_LARGE")
        try:
            return json.loads(data, parse_float=Decimal)
        except (ValueError, UnicodeError, RecursionError):
            raise SourceError("INVALID_JSON") from None

    def download(self, asset: Asset, store: ObjectStore) -> ObjectRef:
        if requires_proof(asset.model_dump(mode="json")) and not self.staged_downloads:
            raise SourceError("SOURCE_REVISION_PROOF_REQUIRED")
        try:
            with self._response(asset.source_url) as response:
                length = response.headers.get("Content-Length")
                if length is not None and int(length) != asset.size:
                    raise SourceError("SOURCE_CHANGED")

                def chunks() -> Iterator[bytes]:
                    while chunk := response.read1(1024 * 1024):
                        yield chunk

                return store.write(
                    chunks(),
                    expected_size=asset.size,
                    expected_sha256=asset.provider_sha256,
                    expected_git_sha1=asset.git_blob_sha1,
                )
        except ValueError:
            raise SourceError("SOURCE_INTEGRITY_FAILED") from None


def discover(transport: NflverseTransport) -> Catalog:
    def releases(repo: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for page in range(1, 81):
            rows = transport.json(
                f"https://api.github.com/repos/{repo}/releases?per_page=5&page={page}"
            )
            if not isinstance(rows, list):
                raise SourceError("SCHEMA_DRIFT")
            if not rows:
                return result
            result.extend(rows)
        raise SourceError("CATALOG_PAGE_LIMIT")

    core = releases("nflverse/nflverse-data")
    opportunity = releases("ffverse/ffopportunity")
    branch = transport.json("https://api.github.com/repos/dynastyprocess/data/branches/master")
    commit = branch["commit"]["sha"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise SourceError("SCHEMA_DRIFT")
    directory = transport.json(
        f"https://api.github.com/repos/dynastyprocess/data/contents/files?ref={commit}"
    )
    if not isinstance(directory, list):
        raise SourceError("SCHEMA_DRIFT")
    return build_catalog(core, opportunity, directory, observed_at=datetime.now(UTC))
