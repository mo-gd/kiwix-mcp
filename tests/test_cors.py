"""Tests for CORS support on HTTP transports."""
from __future__ import annotations

from starlette.testclient import TestClient

from kiwix_mcp.app import build_app
from kiwix_mcp.server import create_server

from tests.test_mcp import MockKiwixClient


def _build(transport: str = "streamable-http", cors_origins: str = "*") -> TestClient:
    client = MockKiwixClient()
    mcp = create_server(client, host="127.0.0.1", port=8000)
    app = build_app(client, mcp, transport, cors_origins)
    return TestClient(app)


class TestPreflightNot405:
    """OPTIONS preflight must succeed so browser-based MCP clients are not blocked."""

    def test_streamable_http_options_succeeds(self):
        client = _build(transport="streamable-http")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_sse_options_succeeds(self):
        client = _build(transport="sse")
        resp = client.options(
            "/sse",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


class TestOriginParsing:
    """Comma-separated CORS origins must be parsed and enforced correctly."""

    def test_wildcard_default(self):
        client = _build(cors_origins="*")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://anything.example.com", "Access-Control-Request-Method": "POST"},
        )
        assert resp.headers["access-control-allow-origin"] == "*"

    def test_single_origin_allowed(self):
        client = _build(cors_origins="http://myapp.local:3000")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://myapp.local:3000", "Access-Control-Request-Method": "POST"},
        )
        assert resp.headers["access-control-allow-origin"] == "http://myapp.local:3000"

    def test_single_origin_rejects_other(self):
        client = _build(cors_origins="http://myapp.local:3000")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in resp.headers

    def test_comma_separated_origins(self):
        client = _build(cors_origins="http://app1.example.com, http://app2.example.com")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://app1.example.com", "Access-Control-Request-Method": "POST"},
        )
        assert resp.headers["access-control-allow-origin"] == "http://app1.example.com"
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://app2.example.com", "Access-Control-Request-Method": "POST"},
        )
        assert resp.headers["access-control-allow-origin"] == "http://app2.example.com"

    def test_env_var_style_no_spaces(self):
        client = _build(cors_origins="http://a.example.com,http://b.example.com")
        resp = client.options(
            "/mcp",
            headers={"Origin": "http://b.example.com", "Access-Control-Request-Method": "POST"},
        )
        assert resp.headers["access-control-allow-origin"] == "http://b.example.com"
