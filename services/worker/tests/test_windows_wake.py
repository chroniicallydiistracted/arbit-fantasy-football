"""The Windows wake planner (R-066, OWN-065): when the PC is woken for Arbit's reads.

Runs the real PowerShell script through WSL interop; skipped where Windows PowerShell is absent.
"""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "infra/windows/arbit-wake.ps1"
POWERSHELL = shutil.which("powershell.exe")
ET = ZoneInfo("America/New_York")
pytestmark = pytest.mark.skipif(
    POWERSHELL is None or shutil.which("wslpath") is None, reason="needs Windows PowerShell"
)


def windows_path(path: Path) -> str:
    return subprocess.run(
        ["wslpath", "-w", str(path)], capture_output=True, text=True, check=True
    ).stdout.strip()


def plan(tmp_path, kickoffs, now, days):
    source = tmp_path / "kickoffs.json"
    source.write_text(json.dumps(kickoffs))
    done = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            windows_path(SCRIPT),
            "-Windows",
            "-KickoffsJson",
            windows_path(source),
            "-Now",
            now,
            "-Days",
            str(days),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd="/mnt/c" if Path("/mnt/c").exists() else None,
        timeout=60,
    )
    spans = json.loads(done.stdout.strip() or "[]")
    spans = spans if isinstance(spans, list) else [spans]

    def eastern(text):
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(ET)

    return [
        (eastern(s["start"]).strftime("%a %H:%M"), eastern(s["end"]).strftime("%a %H:%M"))
        for s in spans
    ]


def test_a_sunday_wakes_before_each_kickoff_window_and_merges_the_daily_reads(tmp_path):
    kickoffs = [
        "2026-11-15T14:30:00Z",  # London, 9:30 ET
        "2026-11-15T18:00:00Z",  # 1:00 PM
        "2026-11-15T18:00:00Z",
        "2026-11-15T21:05:00Z",  # 4:05 PM
        "2026-11-15T21:25:00Z",  # 4:25 PM
        "2026-11-16T01:20:00Z",  # Sunday night
        "2026-11-17T01:15:00Z",  # Monday night
    ]
    # One day ahead: Sunday and Monday, Eastern.
    assert plan(tmp_path, kickoffs, "2026-11-15T10:00:00Z", 1) == [
        ("Sun 07:30", "Sun 10:00"),
        ("Sun 11:00", "Sun 13:30"),  # with the noon read
        ("Sun 14:05", "Sun 16:55"),
        ("Sun 18:20", "Sun 20:50"),  # with the 7:15 PM read
        ("Mon 11:55", "Mon 12:20"),
        ("Mon 18:15", "Mon 20:45"),  # with the 7:15 PM read
    ]


def test_a_day_without_games_wakes_only_for_the_two_reads_in_daylight_time(tmp_path):
    # 14 October is Eastern Daylight Time.
    assert plan(tmp_path, [], "2026-10-14T10:00:00Z", 0) == [
        ("Wed 11:55", "Wed 12:20"),
        ("Wed 19:10", "Wed 19:35"),
    ]


def test_windows_already_over_are_not_planned(tmp_path):
    # 10:30 ET: the London window ended at 10:00.
    found = plan(
        tmp_path, ["2026-11-15T14:30:00Z", "2026-11-15T18:00:00Z"], "2026-11-15T15:30:00Z", 0
    )
    assert found[0] == ("Sun 11:00", "Sun 13:30")
