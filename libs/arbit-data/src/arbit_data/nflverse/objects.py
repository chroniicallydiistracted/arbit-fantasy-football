"""Immutable original bytes and derived artifacts; bounded streams, checksums and atomic links."""

import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ObjectRef:
    sha256: str
    path: Path
    size: int


class ObjectStore:
    def __init__(self, root: Path, *, max_bytes: int = 512 * 1024 * 1024):
        self.root, self.max_bytes = root, max_bytes
        root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("INVALID_OBJECT_KEY")
        return self.root / digest

    def verify(self, digest: str) -> ObjectRef:
        path = self.path(digest)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > self.max_bytes:
            raise ValueError("INVALID_OBJECT")
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > self.max_bytes:
                    raise ValueError("OBJECT_TOO_LARGE")
                hasher.update(chunk)
        if hasher.hexdigest() != digest:
            raise ValueError("OBJECT_CHECKSUM_MISMATCH")
        return ObjectRef(digest, path, size)

    def read(self, digest: str) -> bytes:
        return self.verify(digest).path.read_bytes()

    def write(
        self,
        chunks: Iterable[bytes],
        *,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
        expected_git_sha1: str | None = None,
    ) -> ObjectRef:
        if expected_size is not None and (expected_size < 0 or expected_size > self.max_bytes):
            raise ValueError("OBJECT_TOO_LARGE")
        sha = hashlib.sha256()
        git = hashlib.sha1(f"blob {expected_size}\0".encode()) if expected_git_sha1 else None
        temp = self.root / (".pending-" + os.urandom(16).hex())
        size = 0
        try:
            descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as target:
                for chunk in chunks:
                    size += len(chunk)
                    if size > self.max_bytes or expected_size is not None and size > expected_size:
                        raise ValueError("OBJECT_TOO_LARGE")
                    sha.update(chunk)
                    if git is not None:
                        git.update(chunk)
                    target.write(chunk)
                if expected_size is not None and size != expected_size:
                    raise ValueError("SOURCE_SIZE_MISMATCH")
                digest = sha.hexdigest()
                if (
                    expected_sha256 is not None
                    and expected_sha256 != digest
                    or git is not None
                    and git.hexdigest() != expected_git_sha1
                ):
                    raise ValueError("SOURCE_CHECKSUM_MISMATCH")
                target.flush()
                os.fsync(target.fileno())
            destination = self.path(digest)
            try:
                os.link(temp, destination)
            except FileExistsError:
                self.verify(digest)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return ObjectRef(digest, destination, size)
        finally:
            temp.unlink(missing_ok=True)

    def put_json(self, payload: Any) -> ObjectRef:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        return self.write((data,), expected_size=len(data))
