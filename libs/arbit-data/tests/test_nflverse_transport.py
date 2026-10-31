"""Source scope, bounded release pagination and immutable raw-repository references."""

import pytest
from arbit_data.errors import SourceError
from arbit_data.nflverse.transport import discover, validate_url


def test_redirect_and_source_allowlist_rejects_downgrade_credentials_and_arbitrary_hosts():
    validate_url("https://github.com/nflverse/nflverse-data/releases/download/pbp/a.parquet")
    validate_url(
        "https://release-assets.githubusercontent.com/asset?signature=opaque", redirect=True
    )
    for url in (
        "https://127.0.0.1/x",
        "http://github.com/nflverse/nflverse-data/x",
        "https://u:p@github.com/nflverse/nflverse-data/x",
        "https://github.com/attacker/data/x",
        "https://release-assets.githubusercontent.com/a?secret=x",
    ):
        with pytest.raises(SourceError):
            validate_url(url)


def test_discovery_stops_only_on_empty_pages_and_pins_directory_commit():
    class Fake:
        def __init__(self):
            self.calls = []

        def json(self, url):
            self.calls.append(url)
            if "/branches/" in url:
                return {"commit": {"sha": "a" * 40}}
            if "/contents/" in url:
                assert "ref=" + "a" * 40 in url
                return []
            return []

    fake = Fake()
    result = discover(fake)
    assert len(fake.calls) == 4 and result.assets == ()


def test_unbracketed_hashless_download_is_not_implicitly_trusted(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from arbit_data.nflverse.catalog import build_catalog
    from arbit_data.nflverse.objects import ObjectStore
    from arbit_data.nflverse.transport import NflverseTransport
    from test_nflverse_catalog import release

    asset = build_catalog(
        [release("players", ["players.parquet"])], [], [], observed_at=datetime.now(UTC)
    ).assets[0]

    def forbidden(*args, **kwargs):
        raise AssertionError("unit test reached source HTTP")

    monkeypatch.setattr(NflverseTransport, "_response", forbidden)
    with pytest.raises(SourceError, match="SOURCE_REVISION_PROOF_REQUIRED"):
        NflverseTransport().download(asset, ObjectStore(tmp_path))
