"""OpenAPI 3.1.0 specification — one tool: kiwix_search."""
from __future__ import annotations

from typing import Any

SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "servers": [{"url": "/", "description": "Kiwix MCP server"}],
    "info": {
        "title": "Kiwix MCP",
        "version": "1.8.0",
        "description": (
            "Single-tool OpenAPI server for Kiwix ZIM libraries.\n\n"
            "**kiwix_search** — search across all books and return the full content "
            "of the top 3 matching articles in one call.\n\n"
            "MCP transport: `/mcp` (streamable-http)"
        ),
        "contact": {"url": "https://github.com/mo-gd/kiwix-mcp"},
        "license": {"name": "MIT"},
    },
    "paths": {
        "/kiwix_search": {
            "post": {
                "operationId": "kiwix_search",
                "summary": "Search all Kiwix books and return full article content",
                "description": (
                    "Search for articles across all available ZIM books. "
                    "Returns the top 3 results with their full plain-text content, "
                    "article URLs, and viewer links for the user. No follow-up calls needed."
                ),
                "tags": ["kiwix"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SearchInput"},
                            "example": {"query": "how to create an npm organization"},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Top 3 results with full article content",
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
                        "example": "how to create an npm organization",
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
                        "description": "Internal article URL",
                    },
                    "viewer_url": {
                        "type": ["string", "null"],
                        "description": "Browser link for the user to open the article in Kiwix viewer",
                    },
                    "snippet": {"type": ["string", "null"]},
                    "content": {
                        "type": ["string", "null"],
                        "description": "Full article as plain text",
                    },
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
