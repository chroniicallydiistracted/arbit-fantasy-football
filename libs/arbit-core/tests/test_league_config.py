import json
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]


def test_loads_confirmed_league_without_scoring_defaults():
    from arbit_core.config import load_league_config

    result = load_league_config(ROOT / "config/league.json")
    assert result.league_id == "1729878439"
    assert result.season == 2026
    assert not hasattr(result, "points_per_reception")


@pytest.mark.parametrize("change", [{"leagueId": "123"}, {"season": True}, {"season": "2026"}])
def test_rejects_wrong_league_or_invalid_season(tmp_path, change):
    from arbit_core.config import load_league_config

    data = json.loads((ROOT / "config/league.json").read_text())
    data.update(change)
    path = tmp_path / "league.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_league_config(path)


@pytest.mark.parametrize("missing", ["leagueId", "season"])
def test_required_context_cannot_be_inferred(tmp_path, missing):
    from arbit_core.config import load_league_config

    data = json.loads((ROOT / "config/league.json").read_text())
    data.pop(missing)
    path = tmp_path / "league.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        load_league_config(path)
