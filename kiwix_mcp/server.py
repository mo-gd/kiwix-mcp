"""MCP server — two tools only: kiwix_search and kiwix_fetch_article."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kiwix_client import KiwixClient, strip_html
from kiwix_client.parse import SearchResult


_SEARCH_DESCRIPTION = (
    "Search for articles across all Kiwix books. "
    "Returns titles, article URLs (pass to kiwix_fetch_article), "
    "and viewer_url links for users to open articles in their browser."
)

_FETCH_DESCRIPTION = (
    "Fetch the full content of a Kiwix article as plain text. "
    "Use a URL returned by kiwix_search."
)


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
    """Build the MCP server with exactly two tools."""
    mcp = FastMCP("kiwix-mcp", host=host, port=port)
    viewer_origin: str = getattr(client, "viewer_base_url", "")

    @mcp.tool(description=_SEARCH_DESCRIPTION)
    def kiwix_search(query: str) -> str:
        """Search all Kiwix books for articles matching the query.

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
                    results.extend(sr.results[:10])
                except Exception:
                    continue
        else:
            # Single-book server or catalog unavailable — search without scope.
            try:
                sr = client.search(pattern=query, books="", start=0)
                results.extend(sr.results)
            except Exception as exc:
                return f'Search failed: {exc}'

        if not results:
            return f'No results for "{query}".'

        lines = [f'{len(results)} result(s) for "{query}":\n']
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}")
            lines.append(f"   URL: {r.url}")
            vurl = _article_viewer_url(viewer_origin, r.url)
            if vurl:
                lines.append(f"   Viewer: {vurl}")
            if r.snippet:
                snip = r.snippet[:200] + "…" if len(r.snippet) > 200 else r.snippet
                lines.append(f"   {snip}")
            lines.append("")
        return "\n".join(lines)

    @mcp.tool(description=_FETCH_DESCRIPTION)
    def kiwix_fetch_article(url: str) -> str:
        """Fetch a Kiwix article as plain text.

        Args:
            url: Relative article URL from kiwix_search (e.g. '/book/A/Page.html').
        """
        if not url:
            raise ValueError("url is required")
        html = client.fetch_article(url)
        return strip_html(html)

    return mcp
