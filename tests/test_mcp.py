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
# Helpers
# ---------------------------------------------------------------------------

def _run_tool_sync(tool, kwargs: dict) -> str:
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(tool.run(kwargs))
    finally:
        loop.close()


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
        assert _article_viewer_url("http://host:8888", "/some/path") == ""

    def test_empty_origin_returns_empty(self):
        assert _article_viewer_url("", "/content/book/page") == ""


# ---------------------------------------------------------------------------
# kiwix_search — single tool
# ---------------------------------------------------------------------------

_SAMPLE_BOOKS = [
    Book(slug="devdocs_en_npm_2026-05", title="npm", name="devdocs_en_npm",
         summary="", category="devdocs", article_count=300),
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


class TestKiwixSearch:
    def test_returns_title_and_url(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
            article=_ARTICLE_HTML,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "npm-org" in out
        assert "/content/devdocs_en_npm_2026-05/cli/v10/commands/npm-org" in out

    def test_includes_viewer_url(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
            article=_ARTICLE_HTML,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "http://127.0.0.1:18888/viewer#devdocs_en_npm_2026-05/cli/v10/commands/npm-org" in out

    def test_includes_full_article_content(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
            article=_ARTICLE_HTML,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "Manage & create orgs." in out
        assert "<" not in out

    def test_no_results_message(self):
        mcp = create_server(MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=SearchResponse(query="xyzzy", total=0, page_length=25),
            article="",
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "xyzzy"})
        assert 'No results for "xyzzy"' in out

    def test_fetch_error_shows_message_not_crash(self):
        """A failed article fetch should show an error inline, not crash the tool."""
        class FailFetchClient(MockKiwixClient):
            def fetch_article(self, relative_url):
                raise ConnectionError("down")

        mcp = create_server(FailFetchClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
        ))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization"})
        assert "Could not fetch article" in out

    def test_search_failure_returns_error_message(self):
        mcp = create_server(MockKiwixClient(error=ConnectionError("down")))
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "test"})
        assert "Search failed" in out or "failed" in out.lower()

    def test_only_one_tool_registered(self):
        import asyncio
        mcp = create_server(MockKiwixClient())
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 1
        assert tools[0].name == "kiwix_search"


# ---------------------------------------------------------------------------
# category parameter
# ---------------------------------------------------------------------------

class TestCategory:
    def test_known_category_restricts_search(self):
        """category="npm" should search with the mapped slug, not all books."""
        records = {"npm": "devdocs_en_npm_2026-05", "linux": "devdocs_en_man_2026-04"}
        mock = MockKiwixClient(
            books=_SAMPLE_BOOKS,
            search_response=_SAMPLE_SEARCH,
            article=_ARTICLE_HTML,
        )
        received_slugs = []
        original = mock.search
        def capturing(pattern, books="", start=0):
            received_slugs.append(books)
            return original(pattern=pattern, books=books, start=start)
        mock.search = capturing

        mcp = create_server(mock, records=records)
        _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "organization", "category": "npm"})
        assert received_slugs == ["devdocs_en_npm_2026-05"]

    def test_unknown_category_returns_error(self):
        records = {"npm": "devdocs_en_npm_2026-05"}
        mcp = create_server(MockKiwixClient(), records=records)
        out = _run_tool_sync(_tool(mcp, "kiwix_search"), {"query": "test", "category": "python"})
        assert "Unknown category" in out
        assert "npm" in out

    def test_description_lists_categories(self):
        import asyncio
        records = {"npm": "devdocs_en_npm_2026-05", "linux": "devdocs_en_man_2026-04"}
        mcp = create_server(MockKiwixClient(), records=records)
        tools = asyncio.run(mcp.list_tools())
        desc = tools[0].description or ""
        assert "npm" in desc
        assert "linux" in desc


# ---------------------------------------------------------------------------
# parse_records
# ---------------------------------------------------------------------------

class TestParseRecords:
    def test_parses_correctly(self, tmp_path):
        from kiwix_mcp.__main__ import parse_records
        (tmp_path / "racords.env").write_text(
            "devdocs_en_npm_2026-05.zim = npm\n"
            "devdocs_en_man_2026-04.zim = linux\n"
        )
        result = parse_records(str(tmp_path))
        assert result == {
            "npm": "devdocs_en_npm_2026-05",
            "linux": "devdocs_en_man_2026-04",
        }

    def test_missing_file_returns_empty(self, tmp_path):
        from kiwix_mcp.__main__ import parse_records
        assert parse_records(str(tmp_path)) == {}

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        from kiwix_mcp.__main__ import parse_records
        (tmp_path / "racords.env").write_text(
            "# this is a comment\n"
            "\n"
            "devdocs_en_npm_2026-05.zim = npm\n"
        )
        assert parse_records(str(tmp_path)) == {"npm": "devdocs_en_npm_2026-05"}
