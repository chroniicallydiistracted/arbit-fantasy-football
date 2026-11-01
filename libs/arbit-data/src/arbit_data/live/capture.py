"""Private copies of the raw responses the live feed already reads. Adds no provider requests.

Normalizing a response keeps only the fields the code knows, so anything else, such as the
`situation` block ESPN is expected to send only during games, is gone once parsed (R-030). These
copies let scoreboards and play graphics be built and replayed against real game days.

Layout: `objects/<sha256>.json.gz` holds each distinct body once, and `<UTC date>.jsonl` holds one
line per read, so repeated bodies still show when they were seen.
"""

import errno
import gzip
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from arbit_data.errors import SourceError
from arbit_data.live.feed import Transport
from arbit_data.public_sources.requests import SourceRequest
from arbit_data.public_sources.transport import PublicResponse

# Reaching this stops capture and is reported. Nothing is ever deleted automatically.
MAX_STORED_BYTES = 5 * 1024**3


class _CaptureFullError(Exception):
    pass


class CapturingTransport:
    """Wraps the feed's transport. A capture failure is reported and never reaches the feed."""

    def __init__(
        self,
        transport: Transport,
        root: Path,
        *,
        max_bytes: int = MAX_STORED_BYTES,
        on_problem: Callable[[str], None] = lambda _code: None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.transport, self.root, self.max_bytes = transport, root, max_bytes
        self.on_problem, self.clock = on_problem, clock
        self.stored: int | None = None
        self.problem: str | None = None

    def fetch(self, request: SourceRequest) -> PublicResponse:
        try:
            response = self.transport.fetch(request)
        except SourceError as error:
            self._record(request, error=error.code)
            raise
        self._record(request, body=response.body)
        return response

    def _record(
        self, request: SourceRequest, *, body: bytes | None = None, error: str | None = None
    ) -> None:
        try:
            self._write(request, body, error)
        except Exception as failure:  # noqa: BLE001
            # Nothing here may cost a score. Codes only: messages can carry paths.
            code = _code(failure)
            if code != self.problem:
                self.problem = code
                self.on_problem(code)
        else:
            self.problem = None

    def _write(self, request: SourceRequest, body: bytes | None, error: str | None) -> None:
        now = self.clock()
        objects = self.root / "objects"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        objects.mkdir(exist_ok=True, mode=0o700)
        if self.stored is None:
            self.stored = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
        entry: dict[str, object] = {
            "at": now.isoformat(),
            "kind": request.kind,
            "url": request.url,
            "event_id": request.event_id,
            "page": request.page,
        }
        target, compressed = None, b""
        if body is None:
            entry["error"] = error
        else:
            digest = hashlib.sha256(body).hexdigest()
            entry |= {"sha256": digest, "bytes": len(body)}
            target = objects / f"{digest}.json.gz"
            if not target.exists():
                compressed = gzip.compress(body, mtime=0)
        line = (json.dumps(entry, sort_keys=True) + "\n").encode()
        added = len(compressed) + len(line)
        if self.stored + added > self.max_bytes:
            raise _CaptureFullError
        if target is not None and compressed:
            _publish(target, compressed)
        _append(self.root / f"{now.astimezone(UTC):%Y-%m-%d}.jsonl", line)
        self.stored += added


def _publish(target: Path, data: bytes) -> None:
    """A crash can't leave a partial object under its final name."""
    pending = target.with_name(f".pending-{os.urandom(8).hex()}")
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)


def _append(path: Path, line: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(line)


def _code(failure: Exception) -> str:
    if isinstance(failure, _CaptureFullError):
        return "CAPTURE_FULL"
    number = failure.errno if isinstance(failure, OSError) else None
    if number is not None and number in errno.errorcode:
        return f"CAPTURE_{errno.errorcode[number]}"
    return f"CAPTURE_{type(failure).__name__}"
