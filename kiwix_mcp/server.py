"""MCP server — one tool: kiwix_search (search + fetch top 3 results)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kiwix_client import KiwixClient, strip_html
from kiwix_client.parse import SearchResult


_SEARCH_DESCRIPTION = (
    "Search Kiwix books and return the full content of the top 3 matching articles. "
    "No follow-up calls needed — titles, URLs, viewer links, and article text are all included."
)

_TOP_N = 3


def _article_viewer_url(origin: str, article_url: str) -> str:
    """Convert a Kiwix article URL to a browser viewer URL.

    Handles both URL formats returned by kiwix-serve:
      /content/{book}/{path}   → {origin}/viewer#{book}/{path}
      /{book}/A/{path}.html    → {origin}/viewer#{book}/{path}
    """
    if not origin:
        return ""
    path = article_url.lstrip("/")
    if path.startswith("content/"):
        fragment = path[len("content/"):]
    elif "/A/" in path:
        book, rest = path.split("/A/", 1)
        if rest.endswith(".html"):
            rest = rest[:-5]
        fragment = f"{book}/{rest}"
    else:
        return ""
    return f"{origin}/viewer#{fragment}"


def create_server(
    client: KiwixClient,
    host: str = "127.0.0.1",
    port: int = 8000,
    **_ignored,
) -> FastMCP:
    """Build the MCP server with a single search+fetch tool."""
    mcp = FastMCP("kiwix-mcp", host=host, port=port)
    viewer_origin: str = getattr(client, "viewer_base_url", "")

    @mcp.tool(description=_SEARCH_DESCRIPTION)
    def kiwix_search(query: str) -> str:
        """Search all Kiwix books and return full content of the top 3 articles.

        Args:
            query: What to search for.
        """
        if not query:
            raise ValueError("query is required")

        # Discover all books, then search each one.
        try:
            books = client.list_books()
        except Exception:
            books = []

        results: list[SearchResult] = []

        if books:
            for book in books:
                try:
                    sr = client.search(pattern=query, books=book.slug, start=0)
                    results.extend(sr.results[:_TOP_N])
                except Exception:
                    continue
        else:
            try:
                sr = client.search(pattern=query, books="", start=0)
                results.extend(sr.results)
            except Exception as exc:
                return f'Search failed: {exc}'

        if not results:
            return f'No results for "{query}".'

        top = results[:_TOP_N]
        lines = [f'{len(top)} result(s) for "{query}":\n']

        for i, r in enumerate(top, 1):
            vurl = _article_viewer_url(viewer_origin, r.url)
            lines.append(f"{'─' * 60}")
            lines.append(f"{i}. {r.title}")
            lines.append(f"   URL: {r.url}")
            if vurl:
                lines.append(f"   Viewer: {vurl}")
            lines.append("")
            try:
                html = client.fetch_article(r.url)
                content = strip_html(html)
            except Exception as exc:
                content = f"[Could not fetch article: {exc}]"
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    return mcp
