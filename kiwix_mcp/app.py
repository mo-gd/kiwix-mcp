"""ASGI application: OpenAPI tool server + Swagger/ReDoc + MCP transport."""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from kiwix_client import KiwixClient, strip_html
from kiwix_mcp.openapi import SPEC

# ---------------------------------------------------------------------------
# UI templates
# ---------------------------------------------------------------------------

_SWAGGER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kiwix MCP — Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "BaseLayout",
      deepLinking: true,
      tryItOutEnabled: true,
    });
  </script>
</body>
</html>
"""

_REDOC_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kiwix MCP — ReDoc</title>
</head>
<body>
  <redoc spec-url="/openapi.json"></redoc>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Path-rewriting middleware
# ---------------------------------------------------------------------------

# All REST paths served by this app. Used to decide which /mcp/* paths to
# rewrite for clients that treat /mcp as their base URL (e.g. Open WebUI).
_REST_PATHS = frozenset({
    "/openapi.json", "/docs", "/redoc", "/health",
    "/kiwix_search", "/kiwix_fetch_article",
})


class _MCPPrefixMiddleware:
    """Rewrite /mcp/<REST_PATH> → /<REST_PATH> before Starlette routing.

    Open WebUI uses the configured server URL as the base for all calls.
    When the user sets the server URL to http://host/mcp, Open WebUI calls
    /mcp/kiwix_search, /mcp/kiwix_fetch_article, etc.  This middleware strips
    /mcp for known REST paths so the root router can handle them directly.
    Paths not in _REST_PATHS (e.g. /mcp itself for the MCP transport) are
    passed through unchanged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope["path"]
            if path.startswith("/mcp/"):
                stripped = path[4:]  # "/mcp/kiwix_search" → "/kiwix_search"
                if stripped.rstrip("/") in _REST_PATHS or stripped in _REST_PATHS:
                    scope = {**scope, "path": stripped}
        await self._app(scope, receive, send)


# ---------------------------------------------------------------------------
# Viewer URL helper
# ---------------------------------------------------------------------------

def _viewer_url(origin: str, article_url: str) -> Optional[str]:
    """Convert a Kiwix article URL to a browser viewer URL.

    Handles both URL formats returned by kiwix-serve:
      /content/{book}/{path}   → {origin}/viewer#{book}/{path}
      /{book}/A/{path}.html    → {origin}/viewer#{book}/{path}
    """
    if not origin:
        return None
    path = article_url.lstrip("/")
    if path.startswith("content/"):
        fragment = path[len("content/"):]
    elif "/A/" in path:
        book, rest = path.split("/A/", 1)
        if rest.endswith(".html"):
            rest = rest[:-5]
        fragment = f"{book}/{rest}"
    else:
        return None
    return f"{origin}/viewer#{fragment}"


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def build_app(
    client: KiwixClient,
    mcp: FastMCP,
    transport: str,
    cors_origins: str,
) -> Any:
    """Return a fully configured ASGI app.

    Primary endpoints (POST, mcpo-style — what Open WebUI expects):
      POST /kiwix_search        — full-text search across all books
      POST /kiwix_fetch_article — fetch article as plain text

    Discovery / docs:
      GET  /openapi.json        — OpenAPI 3.1.0 spec
      GET  /docs                — Swagger UI
      GET  /redoc               — ReDoc
      GET  /health              — health check

    All paths also reachable with /mcp/ prefix (Open WebUI base-URL behaviour).

    MCP transport:
      *  /mcp   — streamable-http (if selected)
      *  /sse   — SSE (if selected)
    """

    viewer_origin: str = getattr(client, "viewer_base_url", "")

    # -- meta -----------------------------------------------------------------

    async def openapi_json(request: Request) -> JSONResponse:
        return JSONResponse(SPEC)

    async def swagger_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(_SWAGGER_HTML)

    async def redoc_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(_REDOC_HTML)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # -- POST tool endpoints (primary, mcpo-style) ----------------------------

    async def tool_search(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}

        q = body.get("query", "")
        if not q:
            return JSONResponse({"error": "query is required"}, status_code=400)

        # Search all books and aggregate results.
        try:
            books = client.list_books()
        except Exception:
            books = []

        all_results: list = []

        if books:
            for book in books:
                try:
                    sr = client.search(pattern=q, books=book.slug, start=0)
                    all_results.extend(sr.results[:10])
                except Exception:
                    continue
        else:
            try:
                sr = client.search(pattern=q, books="", start=0)
                all_results.extend(sr.results)
            except ValueError as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)
            except Exception as exc:
                return JSONResponse({"error": str(exc)}, status_code=502)

        return JSONResponse({
            "query": q,
            "total": len(all_results),
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "viewer_url": _viewer_url(viewer_origin, r.url),
                    "snippet": r.snippet or None,
                }
                for r in all_results
            ],
        })

    async def tool_fetch_article(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}

        url = body.get("url", "")
        if not url:
            return JSONResponse({"error": "url is required"}, status_code=400)
        try:
            html = client.fetch_article(url)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse({"url": url, "content": strip_html(html)})

    # -- routing --------------------------------------------------------------

    routes: list = [
        Route("/openapi.json", openapi_json, methods=["GET"]),
        Route("/docs", swagger_ui, methods=["GET"]),
        Route("/redoc", redoc_ui, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/kiwix_search", tool_search, methods=["POST"]),
        Route("/kiwix_fetch_article", tool_fetch_article, methods=["POST"]),
    ]

    if transport == "streamable-http":
        routes.append(Mount("/mcp", app=mcp.streamable_http_app()))
    elif transport == "sse":
        routes.append(Mount("/sse", app=mcp.sse_app()))

    starlette_app = Starlette(routes=routes)
    app: ASGIApp = _MCPPrefixMiddleware(starlette_app)

    origins = [o.strip() for o in cors_origins.split(",")]
    return CORSMiddleware(
        app,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
