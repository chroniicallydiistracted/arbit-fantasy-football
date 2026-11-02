"""Optional built application on the API origin with explicit public route limits."""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

SPA_ROUTES = {
    "",
    "front-office",
    "join",
    "login",
    "draft",
    "scout",
    "market",
    "lineup",
    "live",
    "archive",
    "settings",
    "watchlist",
    "model",
}
# Deep links with an identifier serve the same client; the client checks them against the API.
SPA_PATTERNS = (re.compile(r"live/games/[1-9][0-9]{0,19}"),)
PUBLIC_FILES = {
    "sw.js",
    "offline.css",
    "icon-192.png",
    "icon-512.png",
    "manifest.webmanifest",
    "mark.svg",
    "offline.html",
    "licenses/big-shoulders.txt",
    "licenses/libre-franklin.txt",
}
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "::1")


def _is_other_name_for_this_machine(request: Request, public_origin: str | None) -> bool:
    """Browsers treat each loopback name as its own site, so only one has the session and passes
    the sign-in origin check. Hosted origins never match: a proxy decides their host header."""
    origin = urlsplit(public_origin or "")
    return (
        origin.hostname in LOOPBACK_NAMES
        and request.url.hostname in LOOPBACK_NAMES
        and request.url.hostname != origin.hostname
        and request.url.port == origin.port
    )


class StaticAssets(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if response.status_code == 200 else "no-store"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def install_static_shell(app: FastAPI, path: Path | None, public_origin: str | None = None) -> None:
    if path is None or not (path / "index.html").is_file():
        return
    root = path.resolve()
    if (root / "assets").is_dir():
        app.mount(
            "/assets",
            StaticAssets(directory=root / "assets", follow_symlink=False),
            name="static-assets",
        )

    @app.get("/{path:path}", include_in_schema=False)
    def shell(request: Request, path: str) -> Any:
        is_client_route = path in SPA_ROUTES or any(p.fullmatch(path) for p in SPA_PATTERNS)
        filename = "index.html" if is_client_route else path if path in PUBLIC_FILES else None
        if filename is None or not (root / filename).is_file():
            raise HTTPException(404, "NOT_FOUND")
        if _is_other_name_for_this_machine(request, public_origin):
            query = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(
                f"{public_origin}{request.url.path}{query}",
                status_code=307,
                headers={"Cache-Control": "no-store"},
            )
        headers = {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        }
        if filename == "sw.js":
            headers["Service-Worker-Allowed"] = "/"
        return FileResponse(root / filename, headers=headers)
