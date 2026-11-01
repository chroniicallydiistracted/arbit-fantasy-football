from fastapi.testclient import TestClient


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
    for name in ["newsreader.txt", "instrument-sans.txt"]:
        (tmp_path / "licenses" / name).write_text("SIL OPEN FONT LICENSE")
    with TestClient(create_app(RuntimeSettings(web_dist_path=tmp_path))) as client:
        for name in ["newsreader.txt", "instrument-sans.txt"]:
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
