"""Entry point: stdio transport ONLY (line-ext-reader removed the http mode,
which upstream ran without authentication)."""

from .server import mcp


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
