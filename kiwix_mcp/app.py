"""ASGI application: REST API + OpenAPI spec + Swagger/ReDoc + MCP transport."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from typing import Callable

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
  <title>Kiwix MCP API — Swagger UI</title>
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
  <title>Kiwix MCP API — ReDoc</title>
</head>
<body>
  <redoc spec-url="/openapi.json"></redoc>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _serialize_dt(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _book_dict(b: Any) -> dict:
    return {
        "slug": b.slug,
        "title": b.title,
        "name": b.name,
        "summary": b.summary or None,
        "language": b.language or None,
        "category": b.category or None,
        "article_count": b.article_count,
        "updated_at": _serialize_dt(b.updated_at),
    }


# ---------------------------------------------------------------------------
# Path-rewriting middleware
# ---------------------------------------------------------------------------

# Canonical REST paths as declared in the OpenAPI spec.
_REST_PATHS = frozenset({
    "/openapi.json", "/docs", "/redoc",
    "/health", "/config",
    "/books", "/search", "/article",
    "/api/books", "/api/search", "/api/article", "/api/config",
})


class _MCPPrefixMiddleware:
    """Rewrite /mcp/<REST_PATH> → /<REST_PATH> before Starlette routing.

    Open WebUI (and similar clients) use the MCP mount point (/mcp) as their
    base URL and prepend it to every path from the OpenAPI spec, sending
    requests to /mcp/books, /mcp/search, etc.  This middleware strips the
    /mcp prefix for known REST paths so the root Starlette router can handle
    them without relying on nested sub-app routing.

    Paths not in _REST_PATHS (e.g. /mcp itself, /mcp/sessions/…) are passed
    through unchanged so the MCP transport mount handles them normally.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope["path"]
            if path.startswith("/mcp/"):
                stripped = path[4:]  # "/mcp/books" → "/books"
                if stripped.rstrip("/") in _REST_PATHS or stripped in _REST_PATHS:
                    scope = {**scope, "path": stripped}
        await self._app(scope, receive, send)


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

    Exposes:
      GET  /openapi.json       — OpenAPI 3.1.0 spec
      GET  /mcp/openapi.json   — same spec (MCP-conventional path)
      GET  /docs               — Swagger UI
      GET  /redoc              — ReDoc UI
      GET  /health             — health check
      GET  /api/books          — list ZIM books
      GET  /api/search         — full-text search
      GET  /api/article        — fetch article as plain text
      *    /mcp                — MCP streamable-http transport (if selected)
      *    /sse                — MCP SSE transport (if selected)
    """

    # -- meta endpoints -------------------------------------------------------

    async def openapi_json(request: Request) -> JSONResponse:
        return JSONResponse(SPEC)

    async def swagger_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(_SWAGGER_HTML)

    async def redoc_ui(request: Request) -> HTMLResponse:
        return HTMLResponse(_REDOC_HTML)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def config(request: Request) -> JSONResponse:
        return JSONResponse({
            "name": "kiwix-mcp",
            "version": "1.5.0",
            "capabilities": ["books", "search", "article"],
        })

    # -- REST endpoints -------------------------------------------------------

    async def api_books(request: Request) -> JSONResponse:
        q = request.query_params.get("q", "")
        try:
            books = client.list_books(q=q)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse({"count": len(books), "books": [_book_dict(b) for b in books]})

    async def api_search(request: Request) -> JSONResponse:
        q = request.query_params.get("q", "")
        if not q:
            return JSONResponse({"error": "q is required"}, status_code=400)

        book = request.query_params.get("book", "")
        try:
            start = int(request.query_params.get("start", "0"))
        except ValueError:
            return JSONResponse({"error": "start must be an integer"}, status_code=400)

        try:
            sr = client.search(pattern=q, books=book, start=start)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)

        delivered = sr.start_index + len(sr.results)
        has_more = delivered < sr.total
        return JSONResponse({
            "query": sr.query,
            "total": sr.total,
            "start": sr.start_index,
            "page_length": sr.page_length,
            "next_start": (sr.start_index + sr.page_length) if has_more else None,
            "results": [
                {
                    "title": r.title,
                    "book": r.book,
                    "url": r.url,
                    "snippet": r.snippet or None,
                    "word_count": r.word_count or None,
                }
                for r in sr.results
            ],
        })

    async def api_article(request: Request) -> JSONResponse:
        url = request.query_params.get("url", "")
        if not url:
            return JSONResponse({"error": "url is required"}, status_code=400)
        try:
            html = client.fetch_article(url)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=502)
        return JSONResponse({"url": url, "content": strip_html(html)})

    # -- routing --------------------------------------------------------------
    # Single-level routes at the root.  _MCPPrefixMiddleware (applied below)
    # rewrites /mcp/<REST_PATH> → /<REST_PATH> before routing, so Open WebUI
    # clients that prefix everything with /mcp are handled transparently.

    routes: list = [
        Route("/openapi.json", openapi_json, methods=["GET"]),
        Route("/docs", swagger_ui, methods=["GET"]),
        Route("/redoc", redoc_ui, methods=["GET"]),
        Route("/health", health, methods=["GET"]),
        Route("/config", config, methods=["GET"]),
        # Primary paths (spec-canonical)
        Route("/books", api_books, methods=["GET"]),
        Route("/search", api_search, methods=["GET"]),
        Route("/article", api_article, methods=["GET"]),
        # Legacy /api/* aliases
        Route("/api/books", api_books, methods=["GET"]),
        Route("/api/search", api_search, methods=["GET"]),
        Route("/api/article", api_article, methods=["GET"]),
        Route("/api/config", config, methods=["GET"]),
    ]

    if transport == "streamable-http":
        routes.append(Mount("/mcp", app=mcp.streamable_http_app()))
    elif transport == "sse":
        routes.append(Mount("/sse", app=mcp.sse_app()))

    starlette_app = Starlette(routes=routes)

    # Apply path-rewriting middleware so /mcp/* REST calls are rerouted.
    app: ASGIApp = _MCPPrefixMiddleware(starlette_app)

    origins = [o.strip() for o in cors_origins.split(",")]
    return CORSMiddleware(
        app,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
