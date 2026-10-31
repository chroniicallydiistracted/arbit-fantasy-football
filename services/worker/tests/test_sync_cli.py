"""Operator entry points cannot target production or arbitrary databases."""

import pytest
from arbit_worker import main as module


@pytest.mark.parametrize("command", ["sync", "sync-status", "sync-replay"])
def test_sync_commands_require_guarded_local_configuration(monkeypatch, capsys, command):
    monkeypatch.delenv("ARBIT_DATABASE_URL", raising=False)
    args = ["arbit-worker", command]
    if command == "sync":
        args += ["--once"]
    if command == "sync-replay":
        args += ["a" * 64]
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "LOCAL_DATABASE_REQUIRED" in capsys.readouterr().err


def test_sync_rejects_unguarded_database_before_opening_connection(monkeypatch, capsys):
    monkeypatch.setenv(
        "ARBIT_DATABASE_URL", "postgresql+psycopg://u:PRIVATE@127.0.0.1/arbit_production"
    )
    monkeypatch.setattr("sys.argv", ["arbit-worker", "sync", "--once"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    output = capsys.readouterr().err
    assert caught.value.code == 2 and "LOCAL_DATABASE_REQUIRED" in output
    assert "PRIVATE" not in output
