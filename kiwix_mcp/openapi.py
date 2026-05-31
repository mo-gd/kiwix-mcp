"""OpenAPI 3.1.0 specification — two tools: kiwix_search, kiwix_fetch_article."""
from __future__ import annotations

from typing import Any

SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "servers": [{"url": "/", "description": "Kiwix MCP server"}],
    "info": {
        "title": "Kiwix MCP",
        "version": "1.7.0",
        "description": (
            "Two-tool OpenAPI server for Kiwix ZIM libraries.\n\n"
            "1. **kiwix_search** — search across all books, get URLs\n"
            "2. **kiwix_fetch_article** — fetch full article content\n\n"
            "MCP transport: `/mcp` (streamable-http)"
        ),
        "contact": {"url": "https://github.com/mo-gd/kiwix-mcp"},
        "license": {"name": "MIT"},
    },
    "paths": {
        "/kiwix_search": {
            "post": {
                "operationId": "kiwix_search",
                "summary": "Search all Kiwix books",
                "description": (
                    "Search for articles across all available ZIM books. "
                    "Returns titles, URLs, and short excerpts. "
                    "Use the URL with kiwix_fetch_article to read the full article."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SearchInput"},
                            "example": {"query": "how to create an organization"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Search results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SearchResponse"}
                            }
                        },
                    },
                    "400": {
                        "description": "Missing query",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "502": {
                        "description": "Kiwix server unreachable",
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
                "summary": "Fetch a full article as plain text",
                "description": (
                    "Retrieve the complete content of a Kiwix article, stripped of HTML. "
                    "Use a URL returned by kiwix_search."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/FetchInput"},
                            "example": {"url": "/devdocs_en_npm_2026-05/A/cli/npm-org.html"},
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
                        "description": "Missing url",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "502": {
                        "description": "Kiwix server unreachable",
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
                        "description": "OK",
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
            "SearchInput": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for",
                        "example": "how to create an organization",
                    }
                },
            },
            "FetchInput": {
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Article URL from kiwix_search",
                        "example": "/devdocs_en_npm_2026-05/A/cli/npm-org.html",
                    }
                },
            },
            "SearchResult": {
                "type": "object",
                "required": ["title", "url"],
                "properties": {
                    "title": {"type": "string"},
                    "url": {
                        "type": "string",
                        "description": "Pass to kiwix_fetch_article to read the full article",
                    },
                    "viewer_url": {
                        "type": ["string", "null"],
                        "description": "Browser link for the user to open the article in Kiwix viewer",
                    },
                    "snippet": {"type": ["string", "null"]},
                },
            },
            "SearchResponse": {
                "type": "object",
                "required": ["query", "results"],
                "properties": {
                    "query": {"type": "string"},
                    "total": {"type": "integer"},
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
                        "description": "Full article as plain text",
                    },
                },
            },
            "HealthResponse": {
                "type": "object",
                "properties": {"status": {"type": "string", "example": "ok"}},
            },
            "ErrorResponse": {
                "type": "object",
                "properties": {"error": {"type": "string"}},
            },
        }
    },
    "tags": [
        {"name": "kiwix", "description": "Kiwix search and article retrieval"},
        {"name": "meta", "description": "Server health"},
    ],
}
