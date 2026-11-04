"""Write the play script contract and its example.

packages/contracts/schemas/play-script.schema.json comes from `PlayScript`, and
tests/fixtures/live/play-script.example.json is the script for the fixture's touchdown pass.
`pnpm check:contracts` validates the example against the schema, and a test keeps the schema
equal to the model.

Usage: uv run python scripts/live/export_play_script_schema.py
"""

import json
from pathlib import Path

from arbit_data.live.choreography import PlayScript, choreograph
from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, interpret

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "packages/contracts/schemas/play-script.schema.json"
EXAMPLE = ROOT / "tests/fixtures/live/play-script.example.json"
FIXTURE = ROOT / "tests/fixtures/live/play-facts.examples.json"


def main() -> None:
    SCHEMA.write_text(json.dumps(PlayScript.model_json_schema(), indent=2) + "\n")
    case = next(c for c in json.loads(FIXTURE.read_text())["cases"] if c["name"] == "pass_catch_spot_and_missed_pat")
    play = normalize_play(case["play"], case["event_id"], 2026)
    teams = GameTeams.build(case["home"], case["away"], case["home_code"], case["away_code"], case["text_codes"])
    script = choreograph(interpret(play, teams), "pass_catch_spot_and_missed_pat:example")
    assert script is not None
    EXAMPLE.write_text(script.model_dump_json(indent=1) + "\n")
    print(f"Wrote {SCHEMA.relative_to(ROOT)} and {EXAMPLE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
