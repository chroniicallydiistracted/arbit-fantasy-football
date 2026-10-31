import json

import pytest


def test_empty_asset_manifest_check_needs_no_database_or_network(monkeypatch, capsys):
    from arbit_worker.main import main

    monkeypatch.delenv("ARBIT_DATABASE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "assets-check"])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["assets"] == 0 and report["media_requests"] == 0
    assert report["local_asset_ready"] is False


@pytest.mark.parametrize(
    "args",
    [
        ["sleeper-probe", "--season", "2026", "--week", "0"],
        ["live-inspect", "--season", "2026", "--week", "8", "--events", "https://evil.example/"],
    ],
)
def test_invalid_scopes_are_rejected_before_source_calls(monkeypatch, args):
    from arbit_worker.main import main

    monkeypatch.setattr("sys.argv", ["arbit-worker", *args])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2
