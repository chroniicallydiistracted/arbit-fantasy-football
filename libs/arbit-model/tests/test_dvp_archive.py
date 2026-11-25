"""The prospective archive's transaction and recovery (owner directive AUD-01d).

Failures injected at every step the directive lists: during staging, before the final rename,
after the rename but before the ledger append, a killed process, and a concurrent run. Each leaves
a state `recover` resolves without regenerating or overwriting an archive.
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from arbit_model.dvp import archive

NOW = datetime(2026, 12, 2, 12, tzinfo=UTC)
CUTOFF = datetime(2026, 12, 4, 1, 15, tzinfo=UTC)


def week_files(cutoff: datetime = CUTOFF) -> dict[str, bytes]:
    csv, parquet, league = b"game_id,b00\ng,1\n", b"PAR1-fake", b'{"rosters": {}}\n'
    import hashlib

    digest = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
    manifest = {
        "classification": "PROSPECTIVE",
        "generatedAt": (cutoff - timedelta(days=1)).isoformat(),
        "cutoff": cutoff.isoformat(),
        "code": "abc",
        "forecasts": {
            "csvSha256": digest(csv),
            "parquetSha256": digest(parquet),
            "contentSha256": "c",
        },
        "league": {"sha256": digest(league)},
        "inputs": {},
    }
    return {
        "forecasts.parquet": parquet,
        "forecasts.csv": csv,
        "manifest.json": json.dumps(manifest).encode(),
        "league.json": league,
    }


class Crash(Exception):
    pass


def crash_at(point: str):
    def fault(where: str) -> None:
        if where == point:
            raise Crash(where)

    return fault


def test_a_complete_archive_is_atomic_read_only_and_never_overwritten(tmp_path):
    folder = tmp_path / "week-13"
    stored = archive.commit(folder, week_files(), lambda: NOW)
    assert stored["archivedAt"] == NOW and set(stored["files"]) == set(week_files())
    assert all(p.stat().st_mode & 0o222 == 0 for p in folder.iterdir())
    with pytest.raises(FileExistsError, match="never overwritten"):
        archive.commit(folder, week_files(), lambda: NOW)
    assert archive.self_consistent(folder)["ok"]


@pytest.mark.parametrize("point", ["staging", "wrote:forecasts.csv", "before_rename"])
def test_a_failure_before_the_rename_leaves_only_staging_which_recovery_removes(tmp_path, point):
    with pytest.raises(Crash):
        archive.commit(tmp_path / "week-13", week_files(), lambda: NOW, fault=crash_at(point))
    assert not (tmp_path / "week-13").exists()
    actions = archive.recover(tmp_path, [], {}, NOW)
    assert [a["action"] for a in actions] == ["removed-staging"]
    assert not list(tmp_path.glob(f"{archive.STAGING}*"))
    # The week can then be archived normally: nothing was half-written.
    archive.commit(tmp_path / "week-13", week_files(), lambda: NOW)


def test_an_archive_without_its_ledger_entry_is_recovered_before_the_cutoff(tmp_path):
    with pytest.raises(Crash):
        archive.commit(
            tmp_path / "week-13", week_files(), lambda: NOW, fault=crash_at("after_rename")
        )
    before = {p.name: p.read_bytes() for p in (tmp_path / "week-13").iterdir()}
    actions = archive.recover(tmp_path, [], {}, NOW)
    assert [a["action"] for a in actions] == ["recover"]
    assert actions[0]["week"] == 13 and set(actions[0]["files"]) == set(before)
    # Recovery reads; it never rewrites the archive.
    assert {p.name: p.read_bytes() for p in (tmp_path / "week-13").iterdir()} == before
    # Once the ledger names the folder, recovery leaves it alone.
    assert archive.recover(tmp_path, [{"folder": "week-13"}], {}, NOW) == []


def test_an_archive_without_its_ledger_entry_after_the_cutoff_is_missed_unproven(tmp_path):
    archive.commit(tmp_path / "week-13", week_files(), lambda: NOW)
    actions = archive.recover(tmp_path, [], {}, CUTOFF + timedelta(minutes=1))
    assert actions == [{"action": "missed-unproven", "week": 13, "folder": "week-13"}]


def test_an_archive_that_disagrees_with_its_manifest_is_quarantined(tmp_path):
    files = week_files()
    files["forecasts.csv"] = b"tampered\n"
    archive.commit(tmp_path / "week-13", files, lambda: NOW)
    actions = archive.recover(tmp_path, [], {}, NOW)
    assert actions[0]["action"] == "quarantined"
    assert "forecasts.csv differs from the manifest" in actions[0]["problems"]
    assert not (tmp_path / "week-13").exists()  # the week can be forecast again
    assert list(tmp_path.glob(f"week-13{archive.QUARANTINE}*"))


def test_a_concurrent_run_is_refused(tmp_path):
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; from arbit_model.dvp import archive\n"
            f"with archive.exclusive(Path({str(tmp_path)!r})):\n"
            "    print('ready', flush=True); sys.stdin.read()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "ready"
        with pytest.raises(archive.Busy), archive.exclusive(tmp_path):
            pass
    finally:
        assert holder.stdin is not None
        holder.stdin.close()
        holder.wait(10)
    with archive.exclusive(tmp_path):  # free again once the other run ends
        pass


@pytest.mark.parametrize("point", ["wrote:forecasts.csv", "before_rename", "after_rename"])
def test_a_killed_process_leaves_a_recoverable_state(tmp_path, point):
    script = textwrap.dedent(
        f"""
        import json, os, sys
        from datetime import datetime, UTC
        from pathlib import Path
        sys.path.insert(0, {str(Path(__file__).parent)!r})
        from test_dvp_archive import week_files
        from arbit_model.dvp import archive

        def fault(where):
            if where == {point!r}:
                os._exit(9)  # no cleanup, as when the host stops

        archive.commit(Path({str(tmp_path)!r}) / "week-13", week_files(),
                       lambda: datetime.now(UTC), fault=fault)
        """
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, check=False)
    assert done.returncode == 9
    with archive.exclusive(tmp_path):  # the dead process released its lock
        actions = archive.recover(tmp_path, [], {}, NOW)
    expected = "recover" if point == "after_rename" else "removed-staging"
    assert [a["action"] for a in actions] == [expected]
    if expected == "recover":
        assert archive.self_consistent(tmp_path / "week-13")["ok"]
    else:
        assert not (tmp_path / "week-13").exists()


def test_fsync_reaches_every_file_and_folder(tmp_path, monkeypatch):
    synced = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: synced.append(fd) or real(fd))
    archive.commit(tmp_path / "week-13", week_files(), lambda: NOW)
    # Four files written and fsynced, the staging tree again, the staging folder and the parent.
    assert len(synced) >= 4 + 4 + 2
