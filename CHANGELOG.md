# Changelog

## [1.8.0] (2026-05-31)

### Breaking changes

* Reduced to **one MCP tool**: `kiwix_search`.
  `kiwix_fetch_article` removed — `kiwix_search` now automatically fetches
  the full content of the top 3 results and returns everything in a single call.

### Features

* Each search result now includes `content` (full plain text of the article).
* No follow-up tool calls needed — the AI gets titles, URLs, viewer links,
  and full article text in one response.

## [1.7.0] (2026-05-31)

### Breaking changes

* Simplified to **two MCP tools** only — `kiwix_search` and `kiwix_fetch_article`.
  `kiwix_list_books` has been removed. `kiwix_search` now automatically searches
  all available books without requiring the caller to specify a book slug.

### Features

* `kiwix_search` response now includes `viewer_url` — a browser link
  (`{kiwix_host}/viewer#{book}/{article}`) for users to open the article
  directly in the Kiwix web viewer.
* OpenAPI 3.1.0 spec updated to reflect the two-tool layout.

## [1.6.0] (2026-05-30)

### Breaking changes

* REST endpoints renamed and switched to POST to match the Open WebUI / mcpo convention:
  * `POST /kiwix_list_books`   `{ "query": "" }`
  * `POST /kiwix_search`       `{ "query": "...", "book": "...", "start": 0 }`
  * `POST /kiwix_fetch_article` `{ "url": "..." }`
* Legacy `GET /books`, `GET /search`, `GET /article`, `GET /api/*` kept as aliases

## [1.5.0] (2026-05-30)

### Features

* **OpenAPI 3.1.0 support** — HTTP transports now expose a full REST API alongside the MCP transport:
  * `GET /openapi.json` and `GET /mcp/openapi.json` — machine-readable OpenAPI 3.1.0 spec
  * `GET /docs` — Swagger UI (interactive browser)
  * `GET /redoc` — ReDoc documentation
  * `GET /health` — health-check endpoint
  * `GET /api/books` — list ZIM books (JSON)
  * `GET /api/search` — full-text search (JSON, paginated)
  * `GET /api/article` — fetch article as plain text (JSON)
* Startup log now prints all endpoint URLs when running an HTTP transport

## [1.4.0](https://github.com/OscillateLabsLLC/kiwix-mcp/compare/v1.3.0...v1.4.0) (2026-04-24)


### Features

* dynamic tool descriptions + CLI/env overrides (from [#8](https://github.com/OscillateLabsLLC/kiwix-mcp/issues/8)) ([f7b75fe](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/f7b75fed3e8cb5c5d5a72140f5fc3d4f7c30c5ee))
* dynamic tool descriptions + CLI/env overrides (from issue [#8](https://github.com/OscillateLabsLLC/kiwix-mcp/issues/8)) ([f8e2e0c](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/f8e2e0c29890715f696487b14c2341cfbbf8c35f))


### Bug Fixes

* raise ValueError on any 400 from /search ([#8](https://github.com/OscillateLabsLLC/kiwix-mcp/issues/8)) ([eb2ae0d](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/eb2ae0dc58e5817842da386841e2601cfb6ea438))
* raise ValueError on any 400 from /search, not just "confusion-of-tongues" ([#8](https://github.com/OscillateLabsLLC/kiwix-mcp/issues/8)) ([ad1f97b](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/ad1f97b9cc35fccdaa4357faab232d6a93bd327c))

## [1.3.0](https://github.com/OscillateLabsLLC/kiwix-mcp/compare/v1.2.1...v1.3.0) (2026-03-18)


### Features

* add CORS support for browser-based MCP clients ([197a0ea](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/197a0eae51914f7cee8d99bf0e85ffc6b462cad9))

## [1.2.1](https://github.com/OscillateLabsLLC/kiwix-mcp/compare/v1.2.0...v1.2.1) (2026-03-17)


### Documentation

* add CONTRIBUTING.md with just/hatchling dev setup ([b88f656](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/b88f6561c9936c22940bd4ca36bfb1f941d10f25))

## [1.2.0](https://github.com/OscillateLabsLLC/kiwix-mcp/compare/v1.1.0...v1.2.0) (2026-03-08)


### Features

* Docker setup ([13d8992](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/13d8992aa172f059d939c2fdad79ec3a08e69a40))

## [1.1.0](https://github.com/OscillateLabsLLC/kiwix-mcp/compare/v1.0.0...v1.1.0) (2026-03-08)


### Features

* add dockerfile ([e304d42](https://github.com/OscillateLabsLLC/kiwix-mcp/commit/e304d4299afdded5b2ba89dc2889e8195d6bb308))
