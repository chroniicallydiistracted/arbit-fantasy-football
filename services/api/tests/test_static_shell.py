import pytest
from fastapi.testclient import TestClient


def _shell_client(tmp_path, public_origin, base_url):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    (tmp_path / "index.html").write_text("<!doctype html><title>Arbit</title>")
    app = create_app(RuntimeSettings(web_dist_path=tmp_path, public_origin=public_origin))
    return TestClient(app, base_url=base_url, follow_redirects=False)


@pytest.mark.parametrize(
    ("public_origin", "visited", "expected"),
    [
        ("http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:8000"),
        ("http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:8000"),
    ],
)
def test_other_names_for_this_machine_go_to_the_address_sign_in_works_on(
    tmp_path, public_origin, visited, expected
):
    """Browsers treat each name as its own site: no cookie, and sign-in is refused."""
    with _shell_client(tmp_path, public_origin, visited) as client:
        response = client.get("/join?invitation=abc&next=live")
        assert response.status_code == 307
        assert response.headers["location"] == f"{expected}/join?invitation=abc&next=live"
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("public_origin", "visited"),
    [
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("http://127.0.0.1:8000", "http://localhost:9000"),
        # A hosted app sits behind a proxy whose host header this server does not control.
        ("https://ffa.westfam.media", "http://localhost:8000"),
        (None, "http://localhost:8000"),
    ],
)
def test_the_app_is_served_where_no_other_address_applies(tmp_path, public_origin, visited):
    with _shell_client(tmp_path, public_origin, visited) as client:
        assert client.get("/live").status_code == 200


def test_only_real_pages_redirect(tmp_path):
    with _shell_client(tmp_path, "http://127.0.0.1:8000", "http://localhost:8000") as client:
        assert client.get("/unknown").status_code == 404
        assert client.get("/.env").status_code == 404
        assert client.get("/health/live").status_code == 200


def test_built_shell_is_allowlisted_and_private_paths_never_fall_back(tmp_path):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    (tmp_path / "index.html").write_text("<!doctype html><title>Arbit</title>")
    (tmp_path / "sw.js").write_text("// static only")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-abc123.js").write_text("export {}")
    app = create_app(RuntimeSettings(web_dist_path=tmp_path))
    with TestClient(app) as client:
        assert client.get("/front-office").status_code == 200
        assert client.get("/front-office").headers["cache-control"] == "no-store"
        assert client.get("/sw.js").headers["cache-control"] == "no-store"
        assert "immutable" in client.get("/assets/app-abc123.js").headers["cache-control"]
        for path in [
            "/api/v1/me",
            "/auth/status",
            "/internal/league/current",
            "/unknown",
            "/.env",
            "/assets/../index.html",
        ]:
            assert client.get(path).status_code == 404


def test_font_license_notices_are_allowlisted(tmp_path):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    (tmp_path / "index.html").write_text("<!doctype html>")
    (tmp_path / "licenses").mkdir()
    for name in ["big-shoulders.txt", "libre-franklin.txt"]:
        (tmp_path / "licenses" / name).write_text("SIL OPEN FONT LICENSE")
    with TestClient(create_app(RuntimeSettings(web_dist_path=tmp_path))) as client:
        for name in ["big-shoulders.txt", "libre-franklin.txt"]:
            assert client.get(f"/licenses/{name}").text == "SIL OPEN FONT LICENSE"
        assert client.get("/licenses/other.txt").status_code == 404


def test_install_icons_are_explicit_public_assets(tmp_path):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    (tmp_path / "index.html").write_text("<!doctype html>")
    for name in ["icon-192.png", "icon-512.png"]:
        (tmp_path / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    with TestClient(create_app(RuntimeSettings(web_dist_path=tmp_path))) as client:
        for name in ["icon-192.png", "icon-512.png"]:
            response = client.get(f"/{name}")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/png"
        assert client.get("/icon-unapproved.png").status_code == 404


def test_offline_css_is_public_without_relaxing_content_security_policy(tmp_path):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    (tmp_path / "index.html").write_text("<!doctype html>")
    (tmp_path / "offline.html").write_text(
        '<!doctype html><link rel="stylesheet" href="/offline.css">'
    )
    (tmp_path / "offline.css").write_text("body { color: #123; }")
    with TestClient(create_app(RuntimeSettings(web_dist_path=tmp_path))) as client:
        page = client.get("/offline.html")
        assert page.status_code == 200
        assert "style-src 'self'" in page.headers["content-security-policy"]
        assert "unsafe-inline" not in page.headers["content-security-policy"]
        style = client.get("/offline.css")
        assert style.status_code == 200
        assert style.headers["content-type"].startswith("text/css")
