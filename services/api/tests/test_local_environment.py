"""Local operator secrets are created once, private, ignored and never printed."""

import importlib.util
from pathlib import Path


def test_environment_creation_is_private_and_preserves_existing_file(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location(
        "local_environment", Path("scripts/local_environment.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / ".env.local"
    assert module.initialize(path) is True
    original = path.read_text()
    assert "ARBIT_OPERATOR_TOKEN=" in original
    assert path.stat().st_mode & 0o777 == 0o600
    assert module.initialize(path) is False
    assert path.read_text() == original
    assert capsys.readouterr().out == ""
