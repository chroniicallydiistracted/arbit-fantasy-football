"""External commitments to prospective forecast archives (owner directive AUD-01a).

config/dvp/prospective-amendment-1.json, externalEvidence:
- the commitment holds the ledger entry, its hash and every archived file's SHA-256, plus the
  forecasts CSV (NFL teams and numbers only). The league capture is committed only as a hash;
  no roster, team or member identifier, database detail or credential is published;
- it is committed to a dedicated branch of the public repository from a dedicated clone, and
  pushed with a key that can write to this repository only. Development branches and main are
  never touched;
- the pushed bytes are fetched back and compared with the local archive;
- GitHub's repository activity record of the push, not the commit's local date, is the
  external timestamp.
"""

import hashlib
import json
import os
import subprocess
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

AUTHOR = {
    "GIT_AUTHOR_NAME": "Arbit research evidence",
    "GIT_AUTHOR_EMAIL": "research-evidence@arbit.invalid",
    "GIT_COMMITTER_NAME": "Arbit research evidence",
    "GIT_COMMITTER_EMAIL": "research-evidence@arbit.invalid",
}
COMMITMENT_FORMAT = "arbit-dvp-m3-3-prospective-commitment-v1"
SAFE_ENTRY_KEYS = (
    "season",
    "week",
    "classification",
    "generatedAt",
    "archivedAt",
    "recordedAt",
    "cutoff",
    "folder",
    "files",
    "contentSha256",
    "code",
    "previousEntrySha256",
    "entrySha256",
)


class PublicationError(RuntimeError):
    pass


def commitment(entry: Mapping[str, Any], amendment_sha256: str) -> dict[str, Any]:
    """The sanitized record published for a ledger entry: hashes and times only."""
    return {
        "format": COMMITMENT_FORMAT,
        "ledgerEntry": {k: entry[k] for k in SAFE_ENTRY_KEYS if k in entry},
        "amendmentSha256": amendment_sha256,
        "note": "Hashes of the local archive; the league capture appears only as its SHA-256.",
    }


def paths_for(entry: Mapping[str, Any]) -> tuple[str, str]:
    base = f"{entry['season']}/{entry['folder']}"
    return f"{base}/commitment.json", f"{base}/forecasts.csv"


def _git(
    clone: Path, *args: str, env: Mapping[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=clone,
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, **AUTHOR, **(env or {})},
    )


def publish(
    clone: Path,
    remote: str,
    branch: str,
    files: Mapping[str, bytes],
    message: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Commit `files` (path -> bytes) to `branch` in the dedicated clone and push it.

    Idempotent: files already committed with the same bytes are not committed again, and an
    unpushed commit from an earlier failed attempt is pushed as is."""
    clone.mkdir(parents=True, exist_ok=True)
    if not (clone / ".git").exists():
        _git(clone, "init", "-q")
        _git(clone, "remote", "add", "origin", remote)
    _git(clone, "remote", "set-url", "origin", remote)
    fetched = _git(clone, "fetch", "-q", "origin", branch, env=env, check=False)
    if fetched.returncode != 0 and "couldn't find remote ref" not in fetched.stderr:
        raise PublicationError(f"fetch failed: {fetched.stderr.strip()[:300]}")
    local = _git(clone, "rev-parse", "-q", "--verify", f"refs/heads/{branch}", check=False)
    if local.returncode != 0:
        if fetched.returncode == 0:
            _git(clone, "checkout", "-q", "-B", branch, "FETCH_HEAD")
        else:
            _git(clone, "checkout", "-q", "--orphan", branch)
    else:
        _git(clone, "checkout", "-q", branch)
        if fetched.returncode == 0:
            # Keep any local commit not yet pushed; the branch only ever grows.
            merged = _git(clone, "merge", "-q", "--ff-only", "FETCH_HEAD", check=False)
            if merged.returncode != 0:
                ahead = _git(
                    clone, "merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD", check=False
                )
                if ahead.returncode != 0:
                    raise PublicationError("the evidence branch diverged from the local clone")
    changed = False
    for path, data in files.items():
        target = clone / path
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        _git(clone, "add", path)
        changed = True
    if changed:
        _git(clone, "commit", "-q", "-m", message)
    head = _git(clone, "rev-parse", "HEAD").stdout.strip()
    pushed = _git(clone, "push", "-q", "origin", f"HEAD:refs/heads/{branch}", env=env, check=False)
    if pushed.returncode != 0:
        raise PublicationError(f"push failed: {pushed.stderr.strip()[:300]}")
    return {"commit": head, "committed": changed}


def verify_remote(
    clone: Path,
    branch: str,
    commit: str,
    expected: Mapping[str, str],
    env: Mapping[str, str] | None = None,
) -> list[str]:
    """Fetch the branch back and compare each published file's bytes with its expected SHA-256.
    Returns the problems ([] when the remote holds exactly what was archived)."""
    fetched = _git(clone, "fetch", "-q", "origin", branch, env=env, check=False)
    if fetched.returncode != 0:
        return [f"fetch failed: {fetched.stderr.strip()[:200]}"]
    problems = []
    contains = _git(clone, "merge-base", "--is-ancestor", commit, "FETCH_HEAD", check=False)
    if contains.returncode != 0:
        problems.append(f"{commit[:12]} is not on the remote branch")
    for path, digest in expected.items():
        shown = subprocess.run(
            ["git", "show", f"{commit}:{path}"], cwd=clone, capture_output=True, check=False
        )
        if shown.returncode != 0:
            problems.append(f"{path} is not in {commit[:12]}")
        elif hashlib.sha256(shown.stdout).hexdigest() != digest:
            problems.append(f"{path} differs from the archive")
    return problems


def read_activity(slug: str, branch: str) -> list[dict[str, Any]]:
    """GitHub's public repository activity for one branch (no credentials needed)."""
    url = (
        f"https://api.github.com/repos/{slug}/activity"
        f"?ref=refs/heads/{branch}&per_page=100&direction=asc"
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "arbit-research-evidence"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https URL)
        value: list[dict[str, Any]] = json.loads(response.read())
    return value


def external_timestamp(
    clone: Path,
    commit: str,
    activity: Sequence[Mapping[str, Any]],
) -> tuple[str | None, dict[str, Any] | None]:
    """When GitHub first received `commit`: the earliest push or branch creation whose new head
    contains it. Returns (timestamp, the activity record) or (None, None) if not recorded yet."""
    ordered = sorted(
        (a for a in activity if a.get("activity_type") in ("push", "branch_creation")),
        key=lambda a: str(a.get("timestamp")),
    )
    for record in ordered:
        after = str(record.get("after", ""))
        if not after:
            continue
        if after == commit:
            return str(record["timestamp"]), dict(record)
        known = _git(clone, "cat-file", "-e", f"{after}^{{commit}}", check=False)
        if known.returncode != 0:
            continue
        if _git(clone, "merge-base", "--is-ancestor", commit, after, check=False).returncode == 0:
            return str(record["timestamp"]), dict(record)
    return None, None


def before(timestamp: str | None, cutoff: datetime) -> bool:
    if timestamp is None:
        return False
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")) < cutoff


ActivityReader = Callable[[str, str], list[dict[str, Any]]]
