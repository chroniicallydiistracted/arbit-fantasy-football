import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_report_compares_every_play_and_uses_time_matched_summary_offsets(tmp_path):
    nfl, espn = tmp_path / "nfl", tmp_path / "espn"
    nfl.mkdir()
    (espn / "objects").mkdir(parents=True)

    def at(seconds):
        return f"2026-11-06T01:15:{seconds:02d}Z"

    def write(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    whistles = {"11": at(2), "22": at(4)}
    write(
        nfl / "2026-11-06.jsonl",
        [
            {"received_at": at(5), "route": "summaries", "games": {"g": {"offset": 5}}},
            {
                "received_at": at(6),
                "route": "v2",
                "game": "g",
                "fingerprints": {"11": "a", "22": "b"},
                "whistles": whistles,
            },
            {
                "received_at": at(7),
                "published_at": at(8),
                "route": "published",
                "game": "g",
                "introduced": ["e11", "e22"],
            },
            {
                "received_at": at(9),
                "route": "weekly",
                "games": {"g": {"fingerprints": {"11": "a", "22": "b"}, "whistles": whistles}},
            },
            {
                "received_at": at(10),
                "route": "v2",
                "game": "g",
                "fingerprints": {"11": "a2", "22": "b"},
                "whistles": whistles,
            },
            {"received_at": at(11), "route": "summaries", "games": {"g": {"offset": 6}}},
            {
                "received_at": at(12),
                "route": "v2",
                "game": "g",
                "fingerprints": {"11": "a2", "22": "b2"},
                "whistles": whistles,
                "deleted": ["22"],
            },
        ],
    )
    body = json.dumps({"items": [{"id": "e11"}, {"id": "e22"}, {"id": "e99"}]}).encode()
    digest = hashlib.sha256(body).hexdigest()
    (espn / "objects" / f"{digest}.json.gz").write_bytes(gzip.compress(body))
    write(
        espn / "2026-11-06.jsonl",
        [{"at": at(13), "kind": "espn.plays", "event_id": "e", "sha256": digest}],
    )
    browser = tmp_path / "browser.jsonl"
    endpoint = {
        "event": "request",
        "run": "r",
        "host": "api.nfl.com",
        "path": "/live",
        "resource": "fetch",
    }
    write(
        browser,
        [
            {**endpoint, "at": at(10), "id": 1},
            {**endpoint, "at": at(40), "id": 2},
            {"at": at(41), "event": "response", "run": "r", "id": 2, "status": 200},
        ],
    )
    script = Path(__file__).resolve().parents[2] / "scripts/live/analyze_nfl_live.py"
    report = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                str(script),
                "--game",
                "g",
                "--espn-event",
                "e",
                "--from",
                at(0),
                "--until",
                at(55),
                "--nfl-log",
                str(nfl),
                "--espn-capture",
                str(espn),
                "--browser-log",
                str(browser),
            ],
            text=True,
        )
    )
    assert report["timed_arrivals"]["v2"] == {"plays": 2, "median_seconds": 3, "p90_seconds": 4}
    assert report["plays"]["22"]["first"]["app_commit"]["seconds_after_whistle"] == 4
    assert report["plays"]["11"]["first"]["espn"]["seconds_after_whistle"] == 11
    assert report["plays"]["11"]["first"]["weekly"]["seconds_after_whistle"] == 7
    assert [change["summary_offset_changed"] for change in report["payload_revisions"]] == [
        False,
        True,
    ]
    assert report["payload_revisions"][1]["marked_deleted"] is True
    assert report["browser"]["fetch_routes"][0]["median_gap_seconds"] == 30
