"""Tests for the OpenAPI REST API endpoints and spec."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from kiwix_client.parse import Book, SearchResponse, SearchResult
from kiwix_mcp.app import build_app
from kiwix_mcp.openapi import SPEC
from kiwix_mcp.server import create_server

from tests.test_mcp import MockKiwixClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(
    books=None,
    search_response=None,
    article: str = "",
    error=None,
    transport: str = "streamable-http",
) -> TestClient:
    mock = MockKiwixClient(
        books=books or [],
        search_response=search_response or SearchResponse(),
        article=article,
        error=error,
    )
    mcp = create_server(mock, host="127.0.0.1", port=8000, auto_describe=False)
    app = build_app(mock, mcp, transport, "*")
    return TestClient(app, raise_server_exceptions=False)


_SAMPLE_BOOKS = [
    Book(
        id="id1",
        slug="devdocs_en_rust_2025-10",
        title="Rust (2025-10)",
        name="devdocs_en_rust",
        summary="Rust docs",
        language="eng",
        category="devdocs",
        article_count=4200,
        updated_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
    ),
    Book(
        id="id2",
        slug="wikipedia_en_top_2025-01",
        title="Wikipedia Top",
        name="wikipedia_en_top",
        summary="",
        language="eng",
        category="wikipedia",
        article_count=50000,
        updated_at=None,
    ),
]

_SAMPLE_SEARCH = SearchResponse(
    query="vector",
    total=42,
    start_index=0,
    page_length=25,
    results=[
        SearchResult(
            title="Vec",
            book="devdocs_en_rust_2025-10",
            url="/devdocs_en_rust_2025-10/A/std/vec/struct.Vec.html",
            snippet="A growable list type.",
            word_count=2100,
        )
    ],
)


# ---------------------------------------------------------------------------
# OpenAPI spec validity
# ---------------------------------------------------------------------------

class TestOpenAPISpec:
    def test_spec_version(self):
        assert SPEC["openapi"] == "3.1.0"

    def test_required_paths_present(self):
        paths = SPEC["paths"]
        assert "/books" in paths
        assert "/search" in paths
        assert "/article" in paths
        assert "/health" in paths
        assert "/config" in paths

    def test_all_operations_have_operationid(self):
        for path, methods in SPEC["paths"].items():
            for method, op in methods.items():
                assert "operationId" in op, f"Missing operationId on {method.upper()} {path}"

    def test_components_schemas_defined(self):
        schemas = SPEC["components"]["schemas"]
        for name in ("Book", "BooksResponse", "SearchResult", "SearchResponse",
                     "ArticleResponse", "HealthResponse", "ConfigResponse", "ErrorResponse"):
            assert name in schemas, f"Schema {name!r} missing"

    def test_search_result_url_described_as_relative(self):
        url_desc = SPEC["components"]["schemas"]["SearchResult"]["properties"]["url"]["description"]
        assert "article" in url_desc.lower() or "fetch" in url_desc.lower()


# ---------------------------------------------------------------------------
# /openapi.json endpoint
# ---------------------------------------------------------------------------

class TestOpenAPIEndpoint:
    def test_openapi_json_returns_200(self):
        c = _make_client()
        resp = c.get("/openapi.json")
        assert resp.status_code == 200

    def test_openapi_json_content_type(self):
        c = _make_client()
        resp = c.get("/openapi.json")
        assert "application/json" in resp.headers["content-type"]

    def test_mcp_openapi_json_alias(self):
        """Both /openapi.json and /mcp/openapi.json must return the same spec."""
        c = _make_client()
        resp1 = c.get("/openapi.json")
        resp2 = c.get("/mcp/openapi.json")
        assert resp1.json() == resp2.json()

    def test_spec_contains_openapi_version(self):
        c = _make_client()
        data = c.get("/openapi.json").json()
        assert data["openapi"] == "3.1.0"


# ---------------------------------------------------------------------------
# /docs and /redoc
# ---------------------------------------------------------------------------

class TestUIEndpoints:
    def test_docs_returns_html(self):
        c = _make_client()
        resp = c.get("/docs")
        assert resp.status_code == 200
        assert "swagger-ui" in resp.text.lower()

    def test_redoc_returns_html(self):
        c = _make_client()
        resp = c.get("/redoc")
        assert resp.status_code == 200
        assert "redoc" in resp.text.lower()


# ---------------------------------------------------------------------------
# /health and /config
# ---------------------------------------------------------------------------

class TestMeta:
    def test_health_returns_ok(self):
        c = _make_client()
        assert c.get("/health").json() == {"status": "ok"}

    def test_config_returns_server_info(self):
        c = _make_client()
        data = c.get("/config").json()
        assert data["name"] == "kiwix-mcp"
        assert "version" in data
        assert "capabilities" in data

    def test_api_config_alias(self):
        c = _make_client()
        assert c.get("/api/config").status_code == 200


# ---------------------------------------------------------------------------
# GET /books  (primary path matching the spec)
# ---------------------------------------------------------------------------

class TestBooks:
    def test_empty_books(self):
        c = _make_client(books=[])
        resp = c.get("/books")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["books"] == []

    def test_books_returned(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        data = c.get("/books").json()
        assert data["count"] == 2
        slugs = [b["slug"] for b in data["books"]]
        assert "devdocs_en_rust_2025-10" in slugs

    def test_book_fields_present(self):
        c = _make_client(books=_SAMPLE_BOOKS[:1])
        book = c.get("/books").json()["books"][0]
        assert book["slug"] == "devdocs_en_rust_2025-10"
        assert book["title"] == "Rust (2025-10)"
        assert book["article_count"] == 4200
        assert book["language"] == "eng"
        assert book["updated_at"] == "2025-10-01T00:00:00+00:00"

    def test_null_updated_at(self):
        c = _make_client(books=[_SAMPLE_BOOKS[1]])
        assert c.get("/books").json()["books"][0]["updated_at"] is None

    def test_client_error_returns_502(self):
        c = _make_client(error=ConnectionError("unreachable"))
        resp = c.get("/books")
        assert resp.status_code == 502

    def test_legacy_api_alias(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/api/books").json()["count"] == 2


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_missing_q_returns_400(self):
        c = _make_client()
        resp = c.get("/search")
        assert resp.status_code == 400
        assert "q is required" in resp.json()["error"]

    def test_invalid_start_returns_400(self):
        c = _make_client()
        resp = c.get("/search?q=test&start=abc")
        assert resp.status_code == 400

    def test_search_returns_results(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        resp = c.get("/search?q=vector&book=devdocs_en_rust_2025-10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "vector"
        assert data["total"] == 42
        assert len(data["results"]) == 1
        r = data["results"][0]
        assert r["title"] == "Vec"
        assert r["word_count"] == 2100

    def test_pagination_next_start(self):
        sr = SearchResponse(
            query="q", total=50, start_index=0, page_length=25,
            results=[SearchResult(title=f"r{i}", book="b", url=f"/b/A/r{i}") for i in range(25)],
        )
        c = _make_client(search_response=sr)
        assert c.get("/search?q=q").json()["next_start"] == 25

    def test_last_page_next_start_is_null(self):
        sr = SearchResponse(
            query="q", total=10, start_index=0, page_length=25,
            results=[SearchResult(title=f"r{i}", book="b", url=f"/b/A/r{i}") for i in range(10)],
        )
        c = _make_client(search_response=sr)
        assert c.get("/search?q=q").json()["next_start"] is None

    def test_book_scope_error_returns_400(self):
        c = _make_client(error=ValueError("search requires a book scope"))
        assert c.get("/search?q=test").status_code == 400

    def test_upstream_error_returns_502(self):
        c = _make_client(error=ConnectionError("unreachable"))
        assert c.get("/search?q=test").status_code == 502

    def test_legacy_api_alias(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        assert c.get("/api/search?q=vector&book=devdocs_en_rust_2025-10").status_code == 200


# ---------------------------------------------------------------------------
# GET /article
# ---------------------------------------------------------------------------

class TestArticle:
    def test_missing_url_returns_400(self):
        c = _make_client()
        resp = c.get("/article")
        assert resp.status_code == 400
        assert "url is required" in resp.json()["error"]

    def test_returns_plain_text(self):
        html = "<html><body><h1>Vec</h1><p>A growable list &amp; more.</p></body></html>"
        c = _make_client(article=html)
        resp = c.get("/article?url=/devdocs_en_rust_2025-10/A/std/vec/struct.Vec.html")
        assert resp.status_code == 200
        data = resp.json()
        assert "Vec" in data["content"]
        assert "A growable list & more." in data["content"]
        assert "<" not in data["content"]

    def test_url_echoed_in_response(self):
        c = _make_client(article="<p>hi</p>")
        url = "/devdocs_en_rust_2025-10/A/Hi.html"
        assert c.get(f"/article?url={url}").json()["url"] == url

    def test_upstream_error_returns_502(self):
        c = _make_client(error=ConnectionError("unreachable"))
        assert c.get("/article?url=/b/A/X.html").status_code == 502

    def test_legacy_api_alias(self):
        c = _make_client(article="<p>hi</p>")
        assert c.get("/api/article?url=/b/A/X.html").status_code == 200


# ---------------------------------------------------------------------------
# /mcp/* — Open WebUI uses /mcp as base URL, so all paths appear prefixed.
# Tests cover both new primary paths (/mcp/search) and legacy (/mcp/api/search).
# ---------------------------------------------------------------------------

class TestMCPPrefixedRoutes:
    """Regression: /mcp/* paths must not be swallowed by the MCP transport mount."""

    def test_mcp_openapi_json(self):
        c = _make_client()
        resp = c.get("/mcp/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["openapi"] == "3.1.0"

    def test_mcp_docs(self):
        assert _make_client().get("/mcp/docs").status_code == 200

    def test_mcp_health(self):
        assert _make_client().get("/mcp/health").json() == {"status": "ok"}

    def test_mcp_config(self):
        data = _make_client().get("/mcp/config").json()
        assert data["name"] == "kiwix-mcp"

    def test_mcp_api_config(self):
        assert _make_client().get("/mcp/api/config").status_code == 200

    # Primary paths (spec-canonical, without /api/)
    def test_mcp_books(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/mcp/books").json()["count"] == 2

    def test_mcp_search(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        resp = c.get("/mcp/search?q=vector&book=devdocs_en_rust_2025-10")
        assert resp.status_code == 200
        assert resp.json()["query"] == "vector"

    def test_mcp_search_missing_q(self):
        assert _make_client().get("/mcp/search").status_code == 400

    def test_mcp_article(self):
        c = _make_client(article="<p>Hello</p>")
        assert "Hello" in c.get("/mcp/article?url=/b/A/X.html").json()["content"]

    # Legacy /api/* aliases under /mcp
    def test_mcp_api_books(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/mcp/api/books").json()["count"] == 2

    def test_mcp_api_search(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        assert c.get("/mcp/api/search?q=vector&book=devdocs_en_rust_2025-10").status_code == 200

    def test_mcp_api_article(self):
        c = _make_client(article="<p>Hello</p>")
        assert c.get("/mcp/api/article?url=/b/A/X.html").status_code == 200
