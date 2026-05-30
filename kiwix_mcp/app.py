"""ASGI application: REST API + OpenAPI spec + Swagger/ReDoc + MCP transport."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

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

    routes = [
        # OpenAPI spec — exact paths first so they are matched before MCP mount
        Route("/openapi.json", openapi_json, methods=["GET"]),
        Route("/mcp/openapi.json", openapi_json, methods=["GET"]),
        # UIs
        Route("/docs", swagger_ui, methods=["GET"]),
        Route("/redoc", redoc_ui, methods=["GET"]),
        # Health
        Route("/health", health, methods=["GET"]),
        # REST API
        Route("/api/books", api_books, methods=["GET"]),
        Route("/api/search", api_search, methods=["GET"]),
        Route("/api/article", api_article, methods=["GET"]),
    ]

    # MCP transport mounts — after exact routes
    if transport == "streamable-http":
        routes.append(Mount("/mcp", app=mcp.streamable_http_app()))
    elif transport == "sse":
        routes.append(Mount("/sse", app=mcp.sse_app()))

    app = Starlette(routes=routes)

    origins = [o.strip() for o in cors_origins.split(",")]
    return CORSMiddleware(
        app,
        allow_origins=origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
