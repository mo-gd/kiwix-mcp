"""Tests for the OpenAPI tool server endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

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
        slug="devdocs_en_npm_2025-10",
        title="npm (2025-10)",
        name="devdocs_en_npm",
        summary="npm docs",
        language="eng",
        category="devdocs",
        article_count=300,
        updated_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
    ),
    Book(
        id="id2",
        slug="devdocs_en_rust_2025-10",
        title="Rust (2025-10)",
        name="devdocs_en_rust",
        summary="",
        language="eng",
        category="devdocs",
        article_count=4200,
        updated_at=None,
    ),
]

_SAMPLE_SEARCH = SearchResponse(
    query="organization",
    total=5,
    start_index=0,
    page_length=25,
    results=[
        SearchResult(
            title="npm-org",
            book="devdocs_en_npm_2025-10",
            url="/devdocs_en_npm_2025-10/A/cli/npm-org.html",
            snippet="Manage orgs.",
            word_count=120,
        )
    ],
)


# ---------------------------------------------------------------------------
# OpenAPI spec validity
# ---------------------------------------------------------------------------

class TestOpenAPISpec:
    def test_version(self):
        assert SPEC["openapi"] == "3.1.0"

    def test_tool_paths_present(self):
        paths = SPEC["paths"]
        assert "/kiwix_list_books" in paths
        assert "/kiwix_search" in paths
        assert "/kiwix_fetch_article" in paths
        assert "/health" in paths

    def test_tools_use_post(self):
        for path in ("/kiwix_list_books", "/kiwix_search", "/kiwix_fetch_article"):
            assert "post" in SPEC["paths"][path], f"{path} must be POST"

    def test_operationids_match_tool_names(self):
        assert SPEC["paths"]["/kiwix_list_books"]["post"]["operationId"] == "kiwix_list_books"
        assert SPEC["paths"]["/kiwix_search"]["post"]["operationId"] == "kiwix_search"
        assert SPEC["paths"]["/kiwix_fetch_article"]["post"]["operationId"] == "kiwix_fetch_article"

    def test_input_schemas_defined(self):
        schemas = SPEC["components"]["schemas"]
        for name in ("ListBooksInput", "SearchInput", "FetchArticleInput"):
            assert name in schemas, f"Schema {name!r} missing"

    def test_search_input_requires_query(self):
        required = SPEC["components"]["schemas"]["SearchInput"].get("required", [])
        assert "query" in required

    def test_fetch_input_requires_url(self):
        required = SPEC["components"]["schemas"]["FetchArticleInput"].get("required", [])
        assert "url" in required


# ---------------------------------------------------------------------------
# /openapi.json
# ---------------------------------------------------------------------------

class TestOpenAPIEndpoint:
    def test_returns_200(self):
        assert _make_client().get("/openapi.json").status_code == 200

    def test_content_type_json(self):
        resp = _make_client().get("/openapi.json")
        assert "application/json" in resp.headers["content-type"]

    def test_mcp_prefix_alias(self):
        c = _make_client()
        assert c.get("/openapi.json").json() == c.get("/mcp/openapi.json").json()

    def test_spec_version_in_response(self):
        assert _make_client().get("/openapi.json").json()["openapi"] == "3.1.0"


# ---------------------------------------------------------------------------
# GET /docs  /redoc  /health
# ---------------------------------------------------------------------------

class TestMeta:
    def test_docs_returns_swagger(self):
        resp = _make_client().get("/docs")
        assert resp.status_code == 200
        assert "swagger-ui" in resp.text.lower()

    def test_redoc_returns_html(self):
        resp = _make_client().get("/redoc")
        assert resp.status_code == 200
        assert "redoc" in resp.text.lower()

    def test_health(self):
        assert _make_client().get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /kiwix_list_books
# ---------------------------------------------------------------------------

class TestToolListBooks:
    def test_empty_body_returns_all_books(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        resp = c.post("/kiwix_list_books", json={})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_no_body_also_works(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        resp = c.post("/kiwix_list_books")
        assert resp.status_code == 200

    def test_query_filters(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        resp = c.post("/kiwix_list_books", json={"query": "npm"})
        assert resp.status_code == 200

    def test_book_fields(self):
        c = _make_client(books=_SAMPLE_BOOKS[:1])
        book = c.post("/kiwix_list_books", json={}).json()["books"][0]
        assert book["slug"] == "devdocs_en_npm_2025-10"
        assert book["title"] == "npm (2025-10)"
        assert book["article_count"] == 300
        assert book["updated_at"] == "2025-10-01T00:00:00+00:00"

    def test_null_updated_at(self):
        c = _make_client(books=[_SAMPLE_BOOKS[1]])
        assert c.post("/kiwix_list_books", json={}).json()["books"][0]["updated_at"] is None

    def test_upstream_error_502(self):
        c = _make_client(error=ConnectionError("down"))
        assert c.post("/kiwix_list_books", json={}).status_code == 502


# ---------------------------------------------------------------------------
# POST /kiwix_search
# ---------------------------------------------------------------------------

class TestToolSearch:
    def test_missing_query_returns_400(self):
        c = _make_client()
        resp = c.post("/kiwix_search", json={})
        assert resp.status_code == 400
        assert "query" in resp.json()["error"]

    def test_invalid_start_returns_400(self):
        c = _make_client()
        resp = c.post("/kiwix_search", json={"query": "test", "start": "bad"})
        assert resp.status_code == 400

    def test_search_returns_results(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        resp = c.post("/kiwix_search", json={
            "query": "organization",
            "book": "devdocs_en_npm_2025-10",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "organization"
        assert data["total"] == 5
        assert len(data["results"]) == 1
        r = data["results"][0]
        assert r["title"] == "npm-org"
        assert r["url"] == "/devdocs_en_npm_2025-10/A/cli/npm-org.html"

    def test_pagination_next_start(self):
        sr = SearchResponse(
            query="q", total=50, start_index=0, page_length=25,
            results=[SearchResult(title=f"r{i}", book="b", url=f"/b/A/r{i}") for i in range(25)],
        )
        c = _make_client(search_response=sr)
        data = c.post("/kiwix_search", json={"query": "q"}).json()
        assert data["next_start"] == 25

    def test_last_page_no_next(self):
        sr = SearchResponse(
            query="q", total=3, start_index=0, page_length=25,
            results=[SearchResult(title=f"r{i}", book="b", url=f"/b/A/r{i}") for i in range(3)],
        )
        c = _make_client(search_response=sr)
        assert c.post("/kiwix_search", json={"query": "q"}).json()["next_start"] is None

    def test_book_scope_error_400(self):
        c = _make_client(error=ValueError("search requires a book scope"))
        assert c.post("/kiwix_search", json={"query": "test"}).status_code == 400

    def test_upstream_error_502(self):
        c = _make_client(error=ConnectionError("down"))
        assert c.post("/kiwix_search", json={"query": "test"}).status_code == 502


# ---------------------------------------------------------------------------
# POST /kiwix_fetch_article
# ---------------------------------------------------------------------------

class TestToolFetchArticle:
    def test_missing_url_returns_400(self):
        c = _make_client()
        resp = c.post("/kiwix_fetch_article", json={})
        assert resp.status_code == 400
        assert "url" in resp.json()["error"]

    def test_returns_plain_text(self):
        html = "<html><body><h1>npm-org</h1><p>Manage &amp; create orgs.</p></body></html>"
        c = _make_client(article=html)
        resp = c.post("/kiwix_fetch_article", json={"url": "/devdocs_en_npm_2025-10/A/cli/npm-org.html"})
        assert resp.status_code == 200
        data = resp.json()
        assert "npm-org" in data["content"]
        assert "Manage & create orgs." in data["content"]
        assert "<" not in data["content"]

    def test_url_echoed(self):
        c = _make_client(article="<p>hi</p>")
        url = "/devdocs_en_npm_2025-10/A/npm-org.html"
        assert c.post("/kiwix_fetch_article", json={"url": url}).json()["url"] == url

    def test_upstream_error_502(self):
        c = _make_client(error=ConnectionError("down"))
        assert c.post("/kiwix_fetch_article", json={"url": "/b/A/X.html"}).status_code == 502


# ---------------------------------------------------------------------------
# /mcp/* prefix — Open WebUI uses the server URL (e.g. http://host/mcp) as
# base for all calls, prepending /mcp to every path from the spec.
# ---------------------------------------------------------------------------

class TestMCPPrefixedRoutes:
    """_MCPPrefixMiddleware must transparently rewrite /mcp/* to /*."""

    def test_mcp_openapi_json(self):
        c = _make_client()
        resp = c.get("/mcp/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["openapi"] == "3.1.0"

    def test_mcp_docs(self):
        assert _make_client().get("/mcp/docs").status_code == 200

    def test_mcp_health(self):
        assert _make_client().get("/mcp/health").json() == {"status": "ok"}

    # Primary POST tool paths under /mcp/
    def test_mcp_list_books(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        resp = c.post("/mcp/kiwix_list_books", json={})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_mcp_search(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        resp = c.post("/mcp/kiwix_search", json={"query": "organization", "book": "devdocs_en_npm_2025-10"})
        assert resp.status_code == 200
        assert resp.json()["query"] == "organization"

    def test_mcp_search_missing_query(self):
        assert _make_client().post("/mcp/kiwix_search", json={}).status_code == 400

    def test_mcp_fetch_article(self):
        c = _make_client(article="<p>Hello</p>")
        resp = c.post("/mcp/kiwix_fetch_article", json={"url": "/b/A/X.html"})
        assert resp.status_code == 200
        assert "Hello" in resp.json()["content"]

    # Legacy GET aliases still work under /mcp/
    def test_mcp_books_get(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/mcp/books").json()["count"] == 2

    def test_mcp_search_get(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        assert c.get("/mcp/search?q=organization&book=devdocs_en_npm_2025-10").status_code == 200

    def test_mcp_article_get(self):
        c = _make_client(article="<p>hi</p>")
        assert c.get("/mcp/article?url=/b/A/X.html").status_code == 200


# ---------------------------------------------------------------------------
# Legacy GET aliases (backward compat)
# ---------------------------------------------------------------------------

class TestLegacyGetAliases:
    def test_get_books(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/books").json()["count"] == 2

    def test_get_search(self):
        c = _make_client(search_response=_SAMPLE_SEARCH)
        assert c.get("/search?q=organization&book=devdocs_en_npm_2025-10").status_code == 200

    def test_get_article(self):
        c = _make_client(article="<p>hi</p>")
        assert c.get("/article?url=/b/A/X.html").status_code == 200

    def test_api_prefix_aliases(self):
        c = _make_client(books=_SAMPLE_BOOKS)
        assert c.get("/api/books").json()["count"] == 2
