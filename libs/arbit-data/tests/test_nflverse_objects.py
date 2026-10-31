"""Immutable streaming objects reject partial writes, bad digests and tampering."""

import hashlib

import pytest
from arbit_data.nflverse.objects import ObjectStore


def test_object_store_streams_and_verifies_existing_bytes(tmp_path):
    store = ObjectStore(tmp_path)
    body = b"column,data\n007,42\n"
    digest = hashlib.sha256(body).hexdigest()
    ref = store.write(iter([body[:3], body[3:]]), expected_size=len(body), expected_sha256=digest)
    assert ref.sha256 == digest
    assert store.read(digest) == body
    assert ref.path.stat().st_mode & 0o777 == 0o600
    assert store.write(iter([body]), expected_size=len(body)).sha256 == digest
    ref.path.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        store.read(digest)
    with pytest.raises(ValueError):
        store.write(iter([body]), expected_size=len(body))


def test_partial_and_oversize_objects_never_publish(tmp_path):
    store = ObjectStore(tmp_path, max_bytes=5)
    for chunks, size, digest in (
        ([b"12"], 3, None),
        ([b"123456"], 6, None),
        ([b"12"], 2, "0" * 64),
    ):
        with pytest.raises(ValueError):
            store.write(iter(chunks), expected_size=size, expected_sha256=digest)
    assert list(tmp_path.glob("[0-9a-f]*")) == []
    for key in ("../secret", "A" * 64, ""):
        with pytest.raises(ValueError):
            store.read(key)
