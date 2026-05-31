"""MCP server — one tool: kiwix_search (search + fetch top 3 results)."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kiwix_client import KiwixClient, strip_html
from kiwix_client.parse import SearchResult


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


def _build_description(records: dict[str, str]) -> str:
    base = (
        "Search Kiwix books and return the full content of the top 3 matching articles. "
        "No follow-up calls needed — titles, URLs, viewer links, and article text are all included."
    )
    if records:
        cats = ", ".join(sorted(records))
        base += (
            f"\n\nAvailable categories: {cats}. "
            "Pass category=<name> to restrict the search to a specific book. "
            "Omit category to search across all books."
        )
    return base


def create_server(
    client: KiwixClient,
    host: str = "127.0.0.1",
    port: int = 8000,
    records: dict[str, str] | None = None,
    **_ignored,
) -> FastMCP:
    """Build the MCP server with a single search+fetch tool.

    Parameters
    ----------
    records:
        Mapping of short category name → ZIM slug, parsed from racords.env.
        E.g. {"npm": "devdocs_en_npm_2026-05", "linux": "devdocs_en_man_2026-04"}.
    """
    _records = records or {}
    mcp = FastMCP("kiwix-mcp", host=host, port=port)
    viewer_origin: str = getattr(client, "viewer_base_url", "")

    @mcp.tool(description=_build_description(_records))
    def kiwix_search(query: str, category: str = "") -> str:
        """Search Kiwix books and return full content of the top 3 articles.

        Args:
            query: What to search for (English keywords only).
            category: Optional category name from racords.env to restrict the search
                      (e.g. "npm", "linux"). Leave empty to search all books.
        """
        if not query:
            raise ValueError("query is required")

        # Resolve category to a book slug.
        book_slug = ""
        if category:
            if category not in _records:
                available = ", ".join(sorted(_records)) or "none configured"
                return f'Unknown category "{category}". Available: {available}.'
            book_slug = _records[category]

        results: list[SearchResult] = []

        if book_slug:
            try:
                sr = client.search(pattern=query, books=book_slug, start=0)
                results.extend(sr.results)
            except Exception as exc:
                return f'Search failed: {exc}'
        else:
            # Search each known book (or fall back to unscoped search).
            try:
                books = client.list_books()
            except Exception:
                books = []

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
