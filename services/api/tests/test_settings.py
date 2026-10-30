import pytest
from pydantic import ValidationError


def test_production_rejects_auth_bypass():
    from arbit_api.settings import RuntimeSettings

    with pytest.raises(ValidationError, match="bypass"):
        RuntimeSettings(environment="production", auth_bypass=True)


def test_settings_and_errors_do_not_reveal_secrets():
    from arbit_api.settings import RuntimeSettings

    settings = RuntimeSettings(
        espn_s2="fixture-private-cookie",
        database_url="postgresql+psycopg://u:private-db@localhost/arbit",
    )
    assert "fixture-private-cookie" not in repr(settings)
    assert "private-db" not in repr(settings)
    with pytest.raises(ValidationError) as error:
        RuntimeSettings(
            environment="production", auth_bypass=True, espn_s2="fixture-private-cookie"
        )
    assert "fixture-private-cookie" not in str(error.value)


def test_default_service_bind_is_local_only():
    from arbit_api.settings import RuntimeSettings

    assert RuntimeSettings().bind_host == "127.0.0.1"
