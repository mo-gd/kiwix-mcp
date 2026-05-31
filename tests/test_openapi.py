"""Tests for the OpenAPI tool server endpoints."""
from __future__ import annotations

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
    Book(slug="devdocs_en_npm_2026-05", title="npm", name="devdocs_en_npm",
         summary="", language="eng", category="devdocs", article_count=300),
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

_ARTICLE_HTML = "<html><body><h1>npm-org</h1><p>Manage &amp; create orgs.</p></body></html>"


# ---------------------------------------------------------------------------
# OpenAPI spec validity
# ---------------------------------------------------------------------------

class TestOpenAPISpec:
    def test_version(self):
        assert SPEC["openapi"] == "3.1.0"

    def test_single_tool_path(self):
        assert "/kiwix_search" in SPEC["paths"]
        assert "/kiwix_fetch_article" not in SPEC["paths"]
        assert "/kiwix_list_books" not in SPEC["paths"]

    def test_health_path_present(self):
        assert "/health" in SPEC["paths"]

    def test_tool_uses_post(self):
        assert "post" in SPEC["paths"]["/kiwix_search"]

    def test_operationid_matches_tool_name(self):
        assert SPEC["paths"]["/kiwix_search"]["post"]["operationId"] == "kiwix_search"

    def test_search_input_requires_query(self):
        required = SPEC["components"]["schemas"]["SearchInput"].get("required", [])
        assert "query" in required

    def test_search_result_has_content_field(self):
        props = SPEC["components"]["schemas"]["SearchResult"]["properties"]
        assert "content" in props
        assert "viewer_url" in props


# ---------------------------------------------------------------------------
# /openapi.json
# ---------------------------------------------------------------------------

class TestOpenAPIEndpoint:
    def test_returns_200(self):
        assert _make_client().get("/openapi.json").status_code == 200

    def test_mcp_prefix_alias(self):
        c = _make_client()
        assert c.get("/openapi.json").json() == c.get("/mcp/openapi.json").json()


# ---------------------------------------------------------------------------
# GET /docs  /redoc  /health
# ---------------------------------------------------------------------------

class TestMeta:
    def test_docs_returns_swagger(self):
        assert "swagger-ui" in _make_client().get("/docs").text.lower()

    def test_redoc_returns_html(self):
        assert "redoc" in _make_client().get("/redoc").text.lower()

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

    def test_returns_results_with_content(self):
        c = _make_client(books=_SAMPLE_BOOKS, search_response=_SAMPLE_SEARCH, article=_ARTICLE_HTML)
        resp = c.post("/kiwix_search", json={"query": "organization"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "organization"
        r = data["results"][0]
        assert r["title"] == "npm-org"
        assert r["url"] == "/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org"
        assert r["viewer_url"] == "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/v10/commands/npm-org"
        assert "npm-org" in r["content"]
        assert "Manage & create orgs." in r["content"]
        assert "<" not in r["content"]

    def test_upstream_error_502(self):
        c = _make_client(error=ConnectionError("down"))
        assert c.post("/kiwix_search", json={"query": "test"}).status_code == 502


# ---------------------------------------------------------------------------
# /mcp/* prefix
# ---------------------------------------------------------------------------

class TestMCPPrefixedRoutes:
    def test_mcp_openapi_json(self):
        assert _make_client().get("/mcp/openapi.json").status_code == 200

    def test_mcp_health(self):
        assert _make_client().get("/mcp/health").json() == {"status": "ok"}

    def test_mcp_search(self):
        c = _make_client(books=_SAMPLE_BOOKS, search_response=_SAMPLE_SEARCH, article=_ARTICLE_HTML)
        resp = c.post("/mcp/kiwix_search", json={"query": "organization"})
        assert resp.status_code == 200
        assert resp.json()["query"] == "organization"
