"""Offline unit tests for the MCP server layer, using a mock client."""
from __future__ import annotations

from typing import List

import pytest

from kiwix_client.parse import Book, SearchResponse, SearchResult
from kiwix_mcp.server import create_server, _article_viewer_url


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MockKiwixClient:
    viewer_base_url = "http://127.0.0.1:18888"

    def __init__(
        self,
        books: List[Book] | None = None,
        search_response: SearchResponse | None = None,
        article: str = "",
        error: Exception | None = None,
    ):
        self._books = books or []
        self._search_response = search_response or SearchResponse()
        self._article = article
        self._error = error

    def list_books(self, q: str = "") -> List[Book]:
        if self._error:
            raise self._error
        return self._books

    def search(self, pattern: str, books: str = "", start: int = 0) -> SearchResponse:
        if self._error:
            raise self._error
        return self._search_response

    def fetch_article(self, relative_url: str) -> str:
        if self._error:
            raise self._error
        return self._article


# ---------------------------------------------------------------------------
# Helpers to invoke MCP tools via FastMCP
# ---------------------------------------------------------------------------

def _run_tool_sync(tool, kwargs: dict) -> str:
    """Run a FastMCP tool synchronously and return text output."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(tool.run(kwargs))
    finally:
        loop.close()
    return result


def _make_server(**kwargs):
    return create_server(MockKiwixClient(**kwargs))


def _tool(mcp, name: str):
    return mcp._tool_manager.get_tool(name)


# ---------------------------------------------------------------------------
# _article_viewer_url helper
# ---------------------------------------------------------------------------

class TestViewerUrl:
    def test_content_format(self):
        url = _article_viewer_url(
            "http://127.0.0.1:18888",
            "/content/devdocs_en_npm_2026-05/creating-an-organization",
        )
        assert url == "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/creating-an-organization"

    def test_content_format_nested(self):
        url = _article_viewer_url(
            "http://127.0.0.1:18888",
            "/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org",
        )
        assert url == "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/v10/commands/npm-org"

    def test_legacy_A_format(self):
        url = _article_viewer_url(
            "http://127.0.0.1:18888",
            "/devdocs_en_npm_2026-05/A/cli/npm-org.html",
        )
        assert url == "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/npm-org"

    def test_no_known_segment_returns_empty(self):
        assert _article_viewer_url("http://host:8888", "/some/path/no-a-segment") == ""

    def test_empty_origin_returns_empty(self):
        assert _article_viewer_url("", "/content/book/page") == ""


# ---------------------------------------------------------------------------
# kiwix_search tool
# ---------------------------------------------------------------------------

_SAMPLE_BOOKS = [
    Book(slug="devdocs_en_npm_2026-05", title="npm", name="devdocs_en_npm",
         summary="", category="devdocs", article_count=300),
    Book(slug="devdocs_en_rust_2026-05", title="Rust", name="devdocs_en_rust",
         summary="", category="devdocs", article_count=4000),
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


class TestKiwixSearch:
    def test_returns_results_from_all_books(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "npm-org" in out
        assert "/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org" in out

    def test_includes_viewer_url(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/v10/commands/npm-org" in out

    def test_no_results_message(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=SearchResponse(query="xyzzy", total=0, page_length=25),
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "xyzzy"})
        assert 'No results for "xyzzy"' in out

    def test_falls_back_to_scopeless_search_when_no_books(self):
        mcp = create_server(MockKiwixClient(
            books=[],
            search_response=_SAMPLE_SEARCH,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "npm-org" in out

    def test_search_failure_returns_error_message(self):
        mcp = create_server(MockKiwixClient(error=ConnectionError("down")))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "test"})
        assert "Search failed" in out or "failed" in out.lower()

    def test_snippet_truncated_at_200_chars(self):
        sr = SearchResponse(
            query="q", total=1, start_index=0, page_length=25,
            results=[SearchResult(title="T", book="b", url="/b/A/p", snippet="x" * 400)],
        )
        mcp = create_server(MockKiwixClient(books=[], search_response=sr))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "q"})
        assert "…" in out


# ---------------------------------------------------------------------------
# kiwix_fetch_article tool
# ---------------------------------------------------------------------------

class TestKiwixFetchArticle:
    def test_returns_plain_text(self):
        html = "<html><body><h1>npm-org</h1><p>Manage &amp; create orgs.</p></body></html>"
        mcp = create_server(MockKiwixClient(article=html))
        out = _run_tool_sync(_tool(mcp, "kiwix_fetch_article"), {"url": "/b/A/npm-org.html"})
        assert "npm-org" in out
        assert "Manage & create orgs." in out
        assert "<" not in out

    def test_upstream_error_propagates(self):
        mcp = create_server(MockKiwixClient(error=ConnectionError("down")))
        with pytest.raises(Exception):
            _run_tool_sync(_tool(mcp, "kiwix_fetch_article"), {"url": "/b/A/X.html"})
