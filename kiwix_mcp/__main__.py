"""Entry point: kiwix-mcp."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_records(zim_dir: str) -> dict[str, str]:
    """Parse racords.env in zim_dir → {short_name: slug}.

    File format (one mapping per line):
        devdocs_en_npm_2026-05.zim = npm
        devdocs_en_man_2026-04.zim = linux
    """
    records: dict[str, str] = {}
    path = Path(zim_dir) / "racords.env"
    if not path.exists():
        return records
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        filename, _, short_name = line.partition("=")
        filename = filename.strip()
        short_name = short_name.strip()
        if filename.endswith(".zim"):
            slug = filename[:-4]  # strip .zim
            records[short_name] = slug
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiwix MCP server")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("KIWIX_BASE_URL", ""),
        help="Kiwix server base URL (or set KIWIX_BASE_URL)",
    )
    parser.add_argument(
        "--zim-dir",
        default=os.environ.get("KIWIX_ZIM_DIR", ""),
        help="Directory containing ZIM files and racords.env (or set KIWIX_ZIM_DIR)",
    )
    parser.add_argument(
        "--transport",
        default=os.environ.get("TRANSPORT", "stdio"),
        choices=["stdio", "sse", "streamable-http"],
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Bind host for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Bind port for HTTP transports (default: 8000)",
    )
    parser.add_argument(
        "--cors-allow-origins",
        default=os.environ.get("CORS_ALLOW_ORIGINS", "*"),
        help="Comma-separated CORS allowed origins (default: '*')",
    )
    args = parser.parse_args()

    if not args.base_url:
        print("error: --base-url or KIWIX_BASE_URL is required", file=sys.stderr)
        sys.exit(1)

    records = parse_records(args.zim_dir) if args.zim_dir else {}
    if records:
        cats = ", ".join(sorted(records))
        print(f"  Categories   : {cats}", file=sys.stderr)

    from kiwix_client import KiwixClient
    from kiwix_mcp.server import create_server

    client = KiwixClient(args.base_url)
    mcp = create_server(client, host=args.host, port=args.port, records=records)

    transport = args.transport
    print(f"kiwix-mcp starting ({transport}) → {args.base_url}", file=sys.stderr)

    if transport in ("streamable-http", "sse"):
        import uvicorn

        from kiwix_mcp.app import build_app

        base = f"http://{args.host}:{args.port}"
        print(f"  OpenAPI spec : {base}/openapi.json", file=sys.stderr)
        print(f"  Swagger UI   : {base}/docs", file=sys.stderr)
        print(f"  ReDoc        : {base}/redoc", file=sys.stderr)
        mcp_path = "/mcp" if transport == "streamable-http" else "/sse"
        print(f"  MCP endpoint : {base}{mcp_path}", file=sys.stderr)

        app = build_app(client, mcp, transport, args.cors_allow_origins, records=records)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
