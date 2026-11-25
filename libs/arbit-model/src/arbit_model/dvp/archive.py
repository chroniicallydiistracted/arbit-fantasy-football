"""Transactional archive of one week's prospective forecasts (owner directive AUD-01d).

config/dvp/prospective-amendment-1.json, archiveTransaction:
- one run at a time (an exclusive lock on the season folder);
- files are staged in a hidden folder, fsynced, then renamed into place in one step and the
  parent fsynced, so a week's folder either exists complete or not at all;
- `archivedAt` is taken after that, so it bounds when the archive became durable;
- what an interrupted run leaves behind is found and resolved by `recover` without ever
  regenerating or overwriting an archived forecast.

Local hash chains and read-only files are tamper evidence, not a guarantee of immutability; the
external commitment (arbit_model.dvp.evidence) is the independent record.
"""

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

STAGING = ".staging-"
QUARANTINE = "-quarantine-"
ARCHIVE_FILES = ("forecasts.parquet", "forecasts.csv", "manifest.json", "league.json")


class Busy(RuntimeError):
    """Another run holds the season's lock."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_tree(path: Path) -> None:
    for item in sorted(path.rglob("*")):
        if item.is_file():
            with item.open("rb") as handle:
                os.fsync(handle.fileno())
    for folder in sorted({p.parent for p in path.rglob("*")} | {path}, reverse=True):
        _fsync_dir(folder)


@contextmanager
def exclusive(root: Path) -> Iterator[None]:
    """Hold the season folder's lock for the whole run, or raise Busy at once."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Busy(f"another run holds {root / '.lock'}") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def no_fault(point: str) -> None:
    """Fault hook for tests: called at each step; production passes this no-op."""


def commit(
    folder: Path,
    files: Mapping[str, bytes],
    clock: Callable[[], datetime],
    inputs: Path | None = None,
    fault: Callable[[str], None] = no_fault,
) -> dict[str, Any]:
    """Stage, fsync and rename a week's files into `folder` atomically. Refuses if it exists.

    Returns each file's SHA-256 and `archivedAt`, taken after the rename is durable."""
    if folder.exists():
        raise FileExistsError(f"{folder} exists; archived forecasts are never overwritten")
    folder.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{STAGING}{folder.name}.", dir=folder.parent))
    fault("staging")
    digests: dict[str, str] = {}
    for name, data in files.items():
        path = staging / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
            os.fsync(fd)
        finally:
            os.close(fd)
        digests[name] = _sha256(data)
        fault(f"wrote:{name}")
    if inputs is not None:
        shutil.move(str(inputs), str(staging / "inputs"))
    _fsync_tree(staging)
    fault("before_rename")
    os.rename(staging, folder)  # one step; fails if another run created the folder meanwhile
    _fsync_dir(folder.parent)
    archived_at = clock()
    for path in folder.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    fault("after_rename")
    return {"files": digests, "archivedAt": archived_at}


def self_consistent(folder: Path) -> dict[str, Any]:
    """Does an archive folder agree with its own manifest? (For recovering one without a ledger
    entry: the manifest records the forecasts' and league capture's hashes.)"""
    problems: list[str] = []
    digests: dict[str, str] = {}
    for name in ARCHIVE_FILES:
        path = folder / name
        if not path.is_file():
            problems.append(f"{name} missing")
            continue
        digests[name] = _sha256(path.read_bytes())
    manifest: dict[str, Any] = {}
    if "manifest.json" in digests:
        try:
            manifest = json.loads((folder / "manifest.json").read_text())
        except ValueError:
            problems.append("manifest.json unreadable")
    if manifest:
        expected = {
            "forecasts.csv": manifest.get("forecasts", {}).get("csvSha256"),
            "forecasts.parquet": manifest.get("forecasts", {}).get("parquetSha256"),
            "league.json": manifest.get("league", {}).get("sha256"),
        }
        for name, digest in expected.items():
            if name in digests and digests[name] != digest:
                problems.append(f"{name} differs from the manifest")
        for name, digest in manifest.get("inputs", {}).items():
            path = folder / "inputs" / name
            if not path.is_file() or _sha256(path.read_bytes()) != digest:
                problems.append(f"inputs/{name} differs from the manifest")
    return {"ok": not problems, "problems": problems, "files": digests, "manifest": manifest}


def _cutoff(week: int, cutoffs: Mapping[int, datetime], manifest: Mapping[str, Any]) -> datetime:
    if week in cutoffs:
        return cutoffs[week]
    return datetime.fromisoformat(str(manifest["cutoff"]))


def recover(
    root: Path,
    ledger: Sequence[Mapping[str, Any]],
    cutoffs: Mapping[int, datetime],
    now: datetime,
) -> list[dict[str, Any]]:
    """Resolve what an interrupted run left in `root`. Returns the actions, for the harness to
    record: staging removed; an archive without a ledger entry recovered (before its cutoff),
    recorded missed (after it) or quarantined (inconsistent). Never regenerates anything."""
    actions: list[dict[str, Any]] = []
    for staging in sorted(root.glob(f"{STAGING}*")):
        shutil.rmtree(staging)
        actions.append({"action": "removed-staging", "path": staging.name})
    recorded = {str(e.get("folder")) for e in ledger if e.get("folder")}
    for folder in sorted(p for p in root.glob("week-[0-9][0-9]") if p.is_dir()):
        if folder.name in recorded:
            continue
        week = int(folder.name.split("-")[1])
        check = self_consistent(folder)
        if not check["ok"]:
            moved = folder.with_name(f"{folder.name}{QUARANTINE}{now:%Y%m%dT%H%M%SZ}")
            os.rename(folder, moved)
            actions.append(
                {
                    "action": "quarantined",
                    "week": week,
                    "path": moved.name,
                    "problems": check["problems"],
                }
            )
        elif now < _cutoff(week, cutoffs, check["manifest"]):
            actions.append(
                {
                    "action": "recover",
                    "week": week,
                    "folder": folder.name,
                    "files": check["files"],
                    "manifest": check["manifest"],
                }
            )
        else:
            actions.append({"action": "missed-unproven", "week": week, "folder": folder.name})
    return actions
