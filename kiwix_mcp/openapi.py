"""OpenAPI 3.1.0 specification for the Kiwix REST API."""
from __future__ import annotations

from typing import Any

SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "info": {
        "title": "Kiwix MCP REST API",
        "version": "1.5.0",
        "description": (
            "REST API for the Kiwix MCP server. Provides access to ZIM books "
            "hosted on a Kiwix server: browse the catalog, full-text search, "
            "and article retrieval as plain text.\n\n"
            "The MCP transport (Model Context Protocol) is available at `/mcp` "
            "(streamable-http) or `/sse` (SSE) for AI agent integration."
        ),
        "contact": {"url": "https://github.com/mo-gd/kiwix-mcp"},
        "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    },
    "paths": {
        "/api/books": {
            "get": {
                "operationId": "listBooks",
                "summary": "List available ZIM books",
                "description": (
                    "Returns all ZIM books available on the connected Kiwix server, "
                    "optionally filtered by a title keyword."
                ),
                "tags": ["books"],
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "required": False,
                        "description": "Title keyword filter (e.g. `wikipedia`)",
                        "schema": {"type": "string", "default": ""},
                        "example": "wikipedia",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Catalog of available books",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/BooksResponse"}
                            }
                        },
                    },
                    "502": {
                        "description": "Upstream Kiwix server unreachable",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        },
        "/api/search": {
            "get": {
                "operationId": "search",
                "summary": "Full-text search across ZIM books",
                "description": (
                    "Search for articles across all books or within a specific book. "
                    "On multi-book servers, the `book` parameter is required — "
                    "call `/api/books` first to discover available slugs. "
                    "Results are paginated at 25 per page; use `start` to paginate."
                ),
                "tags": ["search"],
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "required": True,
                        "description": "Search query",
                        "schema": {"type": "string"},
                        "example": "vector",
                    },
                    {
                        "name": "book",
                        "in": "query",
                        "required": False,
                        "description": "Book slug to restrict the search (e.g. `devdocs_en_rust_2025-10`)",
                        "schema": {"type": "string", "default": ""},
                        "example": "devdocs_en_rust_2025-10",
                    },
                    {
                        "name": "start",
                        "in": "query",
                        "required": False,
                        "description": "Zero-based result offset for pagination (page size is 25)",
                        "schema": {"type": "integer", "default": 0, "minimum": 0},
                        "example": 25,
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Paginated search results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Missing required parameter or book scope required on this server",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "502": {
                        "description": "Upstream Kiwix server unreachable",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        },
        "/api/article": {
            "get": {
                "operationId": "fetchArticle",
                "summary": "Fetch an article as plain text",
                "description": (
                    "Retrieve the full content of a Kiwix article, stripped of HTML tags. "
                    "Use the `url` field returned by `/api/search`."
                ),
                "tags": ["articles"],
                "parameters": [
                    {
                        "name": "url",
                        "in": "query",
                        "required": True,
                        "description": "Relative article URL as returned by `/api/search`",
                        "schema": {"type": "string"},
                        "example": "/devdocs_en_rust_2025-10/A/std/vec/struct.Vec.html",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Article content as plain text",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ArticleResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Missing `url` parameter",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "502": {
                        "description": "Upstream Kiwix server unreachable or article not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        },
        "/health": {
            "get": {
                "operationId": "healthCheck",
                "summary": "Server health check",
                "description": "Returns `ok` when the server is running.",
                "tags": ["meta"],
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"}
                            }
                        },
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "Book": {
                "type": "object",
                "required": ["slug", "title"],
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Unique book identifier used as the `book` parameter in search",
                        "example": "devdocs_en_rust_2025-10",
                    },
                    "title": {"type": "string", "example": "Rust (2025-10)"},
                    "name": {
                        "type": "string",
                        "description": "Book name without date suffix",
                        "example": "devdocs_en_rust",
                    },
                    "summary": {"type": ["string", "null"]},
                    "language": {"type": ["string", "null"], "example": "eng"},
                    "category": {"type": ["string", "null"], "example": "devdocs"},
                    "article_count": {"type": "integer", "example": 4200},
                    "updated_at": {
                        "type": ["string", "null"],
                        "format": "date-time",
                        "example": "2025-10-01T00:00:00+00:00",
                    },
                },
            },
            "BooksResponse": {
                "type": "object",
                "required": ["count", "books"],
                "properties": {
                    "count": {"type": "integer", "example": 3},
                    "books": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Book"},
                    },
                },
            },
            "SearchResult": {
                "type": "object",
                "required": ["title", "book", "url"],
                "properties": {
                    "title": {"type": "string", "example": "Vec"},
                    "book": {
                        "type": "string",
                        "description": "Slug of the book containing this article",
                        "example": "devdocs_en_rust_2025-10",
                    },
                    "url": {
                        "type": "string",
                        "description": "Relative URL — pass to `/api/article` to fetch full content",
                        "example": "/devdocs_en_rust_2025-10/A/std/vec/struct.Vec.html",
                    },
                    "snippet": {
                        "type": ["string", "null"],
                        "description": "Short excerpt from the article",
                    },
                    "word_count": {"type": ["integer", "null"], "example": 2100},
                },
            },
            "SearchResponse": {
                "type": "object",
                "required": ["query", "total", "start", "page_length", "results"],
                "properties": {
                    "query": {"type": "string", "example": "vector"},
                    "total": {"type": "integer", "example": 42},
                    "start": {"type": "integer", "example": 0},
                    "page_length": {"type": "integer", "example": 25},
                    "next_start": {
                        "type": ["integer", "null"],
                        "description": "Pass as `start` for the next page; `null` when no more results",
                        "example": 25,
                    },
                    "results": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/SearchResult"},
                    },
                },
            },
            "ArticleResponse": {
                "type": "object",
                "required": ["url", "content"],
                "properties": {
                    "url": {"type": "string"},
                    "content": {
                        "type": "string",
                        "description": "Full article as plain text (HTML stripped)",
                    },
                },
            },
            "HealthResponse": {
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string", "example": "ok"}
                },
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {"type": "string", "example": "q is required"}
                },
            },
        }
    },
    "tags": [
        {"name": "books", "description": "ZIM book catalog operations"},
        {"name": "search", "description": "Full-text article search"},
        {"name": "articles", "description": "Article content retrieval"},
        {"name": "meta", "description": "Server metadata and health"},
    ],
}
