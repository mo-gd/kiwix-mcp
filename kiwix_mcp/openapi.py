"""OpenAPI 3.1.0 specification for the Kiwix MCP tool server."""
from __future__ import annotations

from typing import Any

SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "servers": [{"url": "/", "description": "Kiwix MCP server"}],
    "info": {
        "title": "Kiwix MCP",
        "version": "1.6.0",
        "description": (
            "OpenAPI tool server for Kiwix ZIM libraries. "
            "Provides three tools: list available books, full-text search, "
            "and article retrieval as plain text.\n\n"
            "MCP transport: `/mcp` (streamable-http) · `/sse` (SSE)"
        ),
        "contact": {"url": "https://github.com/mo-gd/kiwix-mcp"},
        "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    },
    "paths": {
        "/kiwix_list_books": {
            "post": {
                "operationId": "kiwix_list_books",
                "summary": "List available ZIM books",
                "description": (
                    "Returns all ZIM books available on the Kiwix server. "
                    "Optionally filter by title keyword. "
                    "Use the returned `slug` values as the `book` parameter in `kiwix_search`."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ListBooksInput"}
                        }
                    },
                },
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
        "/kiwix_search": {
            "post": {
                "operationId": "kiwix_search",
                "summary": "Full-text search across ZIM books",
                "description": (
                    "Search for articles across all books or within a specific book. "
                    "Call `kiwix_list_books` first to find book slugs. "
                    "On multi-book servers the `book` parameter is required. "
                    "Results are paginated at 25 per page; use `start` to paginate."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SearchInput"}
                        }
                    },
                },
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
                        "description": "Missing required field or book scope required",
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
        "/kiwix_fetch_article": {
            "post": {
                "operationId": "kiwix_fetch_article",
                "summary": "Fetch an article as plain text",
                "description": (
                    "Retrieve the full content of a Kiwix article, stripped of HTML. "
                    "Use the `url` value from `kiwix_search` results."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/FetchArticleInput"}
                        }
                    },
                },
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
                        "description": "Missing `url` field",
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
        "/health": {
            "get": {
                "operationId": "health",
                "summary": "Health check",
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
            "ListBooksInput": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "default": "",
                        "description": "Optional title keyword filter (e.g. `wikipedia`)",
                        "example": "npm",
                    }
                },
            },
            "SearchInput": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                        "example": "how to create an organization",
                    },
                    "book": {
                        "type": "string",
                        "default": "",
                        "description": "Book slug from `kiwix_list_books` (required on multi-book servers)",
                        "example": "devdocs_en_npm_2025-10",
                    },
                    "start": {
                        "type": "integer",
                        "default": 0,
                        "minimum": 0,
                        "description": "Zero-based result offset for pagination (page size 25)",
                    },
                },
            },
            "FetchArticleInput": {
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Relative article URL from `kiwix_search` results",
                        "example": "/devdocs_en_npm_2025-10/A/cli/npm-org.html",
                    }
                },
            },
            "Book": {
                "type": "object",
                "required": ["slug", "title"],
                "properties": {
                    "slug": {
                        "type": "string",
                        "description": "Unique identifier — use as `book` in `kiwix_search`",
                        "example": "devdocs_en_npm_2025-10",
                    },
                    "title": {"type": "string", "example": "npm (2025-10)"},
                    "name": {"type": "string", "example": "devdocs_en_npm"},
                    "summary": {"type": ["string", "null"]},
                    "language": {"type": ["string", "null"], "example": "eng"},
                    "category": {"type": ["string", "null"], "example": "devdocs"},
                    "article_count": {"type": "integer", "example": 300},
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
                    "count": {"type": "integer"},
                    "books": {"type": "array", "items": {"$ref": "#/components/schemas/Book"}},
                },
            },
            "SearchResult": {
                "type": "object",
                "required": ["title", "book", "url"],
                "properties": {
                    "title": {"type": "string"},
                    "book": {"type": "string"},
                    "url": {
                        "type": "string",
                        "description": "Pass to `kiwix_fetch_article`",
                    },
                    "snippet": {"type": ["string", "null"]},
                    "word_count": {"type": ["integer", "null"]},
                },
            },
            "SearchResponse": {
                "type": "object",
                "required": ["query", "total", "start", "page_length", "results"],
                "properties": {
                    "query": {"type": "string"},
                    "total": {"type": "integer"},
                    "start": {"type": "integer"},
                    "page_length": {"type": "integer"},
                    "next_start": {
                        "type": ["integer", "null"],
                        "description": "Use as `start` for next page; null if no more results",
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
                "properties": {"status": {"type": "string", "example": "ok"}},
            },
            "ErrorResponse": {
                "type": "object",
                "required": ["error"],
                "properties": {"error": {"type": "string"}},
            },
        }
    },
    "tags": [
        {"name": "kiwix", "description": "Kiwix ZIM library tools"},
        {"name": "meta", "description": "Server metadata"},
    ],
}
