from pathlib import Path
from urllib.parse import urlsplit


def test_bootstrap_writes_private_join_fragment_without_printing(
    uow, engine, tmp_path, monkeypatch, capsys
):
    from arbit_api import admin

    from services.api.tests.test_oidc import provider_settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(admin, "create_engine", lambda *args, **kwargs: engine)
    output = Path("secrets/admin-invitation.txt")
    admin.write_bootstrap(provider_settings(), "owner@example.test", output)
    link = urlsplit(output.read_text().strip())
    assert link.path == "/join"
    assert len(link.fragment) >= 32 and "=" not in link.fragment
    assert output.stat().st_mode & 0o777 == 0o600
    assert capsys.readouterr().out == ""
