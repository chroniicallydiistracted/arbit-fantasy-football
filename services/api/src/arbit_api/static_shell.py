"""Optional built application on the API origin with explicit public route limits."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import FileResponse, Response
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
PUBLIC_FILES = {
    "sw.js",
    "offline.css",
    "icon-192.png",
    "icon-512.png",
    "manifest.webmanifest",
    "mark.svg",
    "offline.html",
    "licenses/newsreader.txt",
    "licenses/instrument-sans.txt",
}


class StaticAssets(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if response.status_code == 200 else "no-store"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def install_static_shell(app: FastAPI, path: Path | None) -> None:
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
        filename = "index.html" if path in SPA_ROUTES else path if path in PUBLIC_FILES else None
        if filename is None or not (root / filename).is_file():
            raise HTTPException(404, "NOT_FOUND")
        headers = {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        }
        if filename == "sw.js":
            headers["Service-Worker-Allowed"] = "/"
        return FileResponse(root / filename, headers=headers)
