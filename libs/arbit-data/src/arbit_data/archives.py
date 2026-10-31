"""Private, content-addressed parsed/redacted captures; never a public file service."""

import gzip
import hashlib
import io
import os
import zlib
from pathlib import Path
from typing import Any, Literal, Self

from arbit_core.identity import require_aware
from pydantic import model_validator

from arbit_data.contracts import DataModel
from arbit_data.espn.contracts import EspnAcquisition

MAX_CAPTURE_BYTES = 32 * 1024 * 1024


class CapturedInput(DataModel):
    format: Literal["ffa-parsed-redacted-v1"] = "ffa-parsed-redacted-v1"
    adapter_version: Literal["ffa-canonical-v1"] = "ffa-canonical-v1"
    acquisition: EspnAcquisition
    verification: dict[str, Any] | None

    @model_validator(mode="after")
    def valid_window(self) -> Self:
        item = self.acquisition
        require_aware(item.capture_started_at)
        require_aware(item.capture_finished_at)
        if item.capture_finished_at < item.capture_started_at or not item.receipts:
            raise ValueError("invalid capture window or missing receipts")
        for receipt in item.receipts:
            require_aware(receipt.observed_at)
            if not item.capture_started_at <= receipt.observed_at <= item.capture_finished_at:
                raise ValueError("receipt outside capture window")
            if (
                len(receipt.sha256) != 64
                or any(c not in "0123456789abcdef" for c in receipt.sha256)
                or receipt.byte_count < 0
            ):
                raise ValueError("invalid source receipt")
        return self


class CaptureArchive:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid capture hash")
        return self.root / (digest + ".json.gz")

    def write(self, capture: CapturedInput) -> str:
        capture = CapturedInput.model_validate(capture.model_dump())
        data = capture.model_dump_json().encode()
        if len(data) > MAX_CAPTURE_BYTES:
            raise ValueError("capture exceeds bound")
        digest = hashlib.sha256(data).hexdigest()
        path = self.path(digest)
        compressed = gzip.compress(data, mtime=0)
        # Atomic link publishes a fully fsynced file. Existing objects are verified, never replaced.
        temporary = self.root / (".pending-" + os.urandom(16).hex())
        try:
            with temporary.open("xb") as target:
                os.chmod(temporary, 0o600)
                target.write(compressed)
                target.flush()
                os.fsync(target.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                self.read(digest)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        return digest

    def read(self, digest: str) -> CapturedInput:
        path = self.path(digest)
        if path.is_symlink() or path.stat().st_size > MAX_CAPTURE_BYTES:
            raise ValueError("invalid or oversized capture")
        try:
            with path.open("rb") as source, gzip.GzipFile(fileobj=source) as stream:
                data = stream.read(MAX_CAPTURE_BYTES + 1)
            if len(data) > MAX_CAPTURE_BYTES or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("invalid capture integrity")
            return CapturedInput.model_validate_json(data)
        except (OSError, EOFError, io.UnsupportedOperation, zlib.error) as error:
            raise ValueError("invalid capture") from error
