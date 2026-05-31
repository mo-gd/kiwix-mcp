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
    mcp = create_server(mock, host="127.0.0.1", port=8000)
    app = build_app(mock, mcp, transport, "*")
    return TestClient(app, raise_server_exceptions=False)


_SAMPLE_BOOKS = [
    Book(
        id="id1",
        slug="devdocs_en_npm_2026-05",
        title="npm (2026-05)",
        name="devdocs_en_npm",
        summary="npm docs",
        language="eng",
        category="devdocs",
        article_count=300,
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    ),
    Book(
        id="id2",
        slug="devdocs_en_rust_2026-05",
        title="Rust (2026-05)",
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
    total=1,
    start_index=0,
    page_length=25,
    results=[
        SearchResult(
            title="npm-org",
            book="devdocs_en_npm_2026-05",
            url="/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org",
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

    def test_exactly_two_tool_paths(self):
        paths = SPEC["paths"]
        assert "/kiwix_search" in paths
        assert "/kiwix_fetch_article" in paths
        assert "/kiwix_list_books" not in paths

    def test_health_path_present(self):
        assert "/health" in SPEC["paths"]

    def test_tools_use_post(self):
        for path in ("/kiwix_search", "/kiwix_fetch_article"):
            assert "post" in SPEC["paths"][path], f"{path} must be POST"

    def test_operationids_match_tool_names(self):
        assert SPEC["paths"]["/kiwix_search"]["post"]["operationId"] == "kiwix_search"
        assert SPEC["paths"]["/kiwix_fetch_article"]["post"]["operationId"] == "kiwix_fetch_article"

    def test_search_input_requires_query(self):
        required = SPEC["components"]["schemas"]["SearchInput"].get("required", [])
        assert "query" in required

    def test_fetch_input_requires_url(self):
        required = SPEC["components"]["schemas"]["FetchInput"].get("required", [])
        assert "url" in required

    def test_search_result_has_viewer_url_field(self):
        props = SPEC["components"]["schemas"]["SearchResult"]["properties"]
        assert "viewer_url" in props


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
# POST /kiwix_search
# ---------------------------------------------------------------------------

class TestToolSearch:
    def test_missing_query_returns_400(self):
        resp = _make_client().post("/kiwix_search", json={})
        assert resp.status_code == 400
        assert "query" in resp.json()["error"]

    def test_search_returns_results(self):
        c = _make_client(books=_SAMPLE_BOOKS, search_response=_SAMPLE_SEARCH)
        resp = c.post("/kiwix_search", json={"query": "organization"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "organization"
        assert len(data["results"]) >= 1
        r = data["results"][0]
        assert r["title"] == "npm-org"
        assert r["url"] == "/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org"

    def test_search_result_includes_viewer_url(self):
        c = _make_client(books=_SAMPLE_BOOKS, search_response=_SAMPLE_SEARCH)
        resp = c.post("/kiwix_search", json={"query": "organization"})
        assert resp.status_code == 200
        r = resp.json()["results"][0]
        assert r["viewer_url"] == (
            "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/v10/commands/npm-org"
        )

    def test_empty_query_returns_400(self):
        resp = _make_client().post("/kiwix_search", json={"query": ""})
        assert resp.status_code == 400

    def test_upstream_error_502(self):
        c = _make_client(error=ConnectionError("down"))
        assert c.post("/kiwix_search", json={"query": "test"}).status_code == 502


# ---------------------------------------------------------------------------
# POST /kiwix_fetch_article
# ---------------------------------------------------------------------------

class TestToolFetchArticle:
    def test_missing_url_returns_400(self):
        resp = _make_client().post("/kiwix_fetch_article", json={})
        assert resp.status_code == 400
        assert "url" in resp.json()["error"]

    def test_returns_plain_text(self):
        html = "<html><body><h1>npm-org</h1><p>Manage &amp; create orgs.</p></body></html>"
        c = _make_client(article=html)
        resp = c.post("/kiwix_fetch_article", json={"url": "/devdocs_en_npm_2026-05/A/cli/npm-org.html"})
        assert resp.status_code == 200
        data = resp.json()
        assert "npm-org" in data["content"]
        assert "Manage & create orgs." in data["content"]
        assert "<" not in data["content"]

    def test_url_echoed(self):
        c = _make_client(article="<p>hi</p>")
        url = "/devdocs_en_npm_2026-05/A/npm-org.html"
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

    def test_mcp_search(self):
        c = _make_client(books=_SAMPLE_BOOKS, search_response=_SAMPLE_SEARCH)
        resp = c.post("/mcp/kiwix_search", json={"query": "organization"})
        assert resp.status_code == 200
        assert resp.json()["query"] == "organization"

    def test_mcp_search_missing_query(self):
        assert _make_client().post("/mcp/kiwix_search", json={}).status_code == 400

    def test_mcp_fetch_article(self):
        c = _make_client(article="<p>Hello</p>")
        resp = c.post("/mcp/kiwix_fetch_article", json={"url": "/b/A/X.html"})
        assert resp.status_code == 200
        assert "Hello" in resp.json()["content"]
