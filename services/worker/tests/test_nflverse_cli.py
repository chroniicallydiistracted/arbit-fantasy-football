"""Statistical import commands retain the local-only guard and safe output boundary."""

import pytest
from arbit_worker import main as module


@pytest.mark.parametrize(
    "command", ["nflverse-catalog", "nflverse-import", "nflverse-status", "nflverse-verify"]
)
def test_nflverse_commands_require_local_profile(monkeypatch, capsys, command):
    monkeypatch.delenv("ARBIT_DATABASE_URL", raising=False)
    args = ["arbit-worker", command]
    if command in ("nflverse-import", "nflverse-status"):
        args += ["--catalog", "a" * 64]
    if command == "nflverse-verify":
        args += ["--all"]
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "LOCAL_DATABASE_REQUIRED" in capsys.readouterr().err
