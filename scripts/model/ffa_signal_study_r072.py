"""The 2026-11-09 signal study, rerun with R-072 repaired, on the exact nflverse files it read.

`ffa_signal_study.py` compares the schedule's team codes (OAK 2016-2019, SD 2016) with the
statistics' (LV, LAC), so it dropped the Raiders' and Chargers' home games and every D/ST game
against them, and 3 of 320 team-seasons fell out of its team rates. The study's file stays
byte-identical (it is part of M3-3 v0, T29). This runs its code unchanged with two substitutions:
every table is read from the manifest the original receipt lists, and every team code is mapped
to its franchise (`arbit_model.teams`) as it is read. The receipt records both.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/ffa_signal_study_r072.py docs/research/ffa-signal-study-2026-11-23-r072.json
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from arbit_data.db import UnitOfWork
from arbit_data.nflverse.objects import ObjectStore
from arbit_model.inputs import NflverseTables
from arbit_model.teams import FRANCHISE, franchise_row

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "scripts/model/ffa_signal_study.py"
ORIGINAL = ROOT / "docs/research/ffa-signal-study-2026-11-09.json"


def load_study() -> Any:
    spec = importlib.util.spec_from_file_location("ffa_signal_study", STUDY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    output = Path(sys.argv[1])
    original = json.loads(ORIGINAL.read_text())
    pins: dict[str, str] = original["nflverseManifests"]
    study = load_study()

    class PinnedFranchiseTables(NflverseTables):
        """The study's `Tables`, reading pinned manifests with franchise team codes."""

        def __init__(self, uow: UnitOfWork, store: ObjectStore) -> None:
            super().__init__(uow, store, pins)

        def read(self, key: str, columns: Any = None) -> list[dict[str, Any]]:
            if key not in pins:
                raise SystemExit(f"the original study did not read {key}")
            return [dict(franchise_row(row)) for row in super().read(key, columns)]

    study.Tables = PinnedFranchiseTables
    sys.argv = [str(STUDY), str(output)]
    study.main()

    report = json.loads(output.read_text())
    if report["nflverseManifests"] != pins:
        raise SystemExit("the rerun read different files from the original")
    report.pop("reportSha256")
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    report["repair"] = {
        "issue": "R-072",
        "task": "TASK-20261123-007",
        "rerunOf": str(ORIGINAL.relative_to(ROOT)),
        "studyFileSha256": hashlib.sha256(STUDY.read_bytes()).hexdigest(),
        "change": "every nflverse team code mapped to its franchise as read; nothing else",
        "franchiseMap": dict(FRANCHISE),
        "inputs": "the original receipt's nflverseManifests, pinned",
        "code": head,
    }
    body = json.dumps(report, indent=1, sort_keys=True)
    report["reportSha256"] = hashlib.sha256(body.encode()).hexdigest()
    output.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
