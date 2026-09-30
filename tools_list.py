"""List the MCP tools in-process (no Chrome, no LINE). Run: .venv/bin/python tools_list.py"""
import asyncio
import sys

sys.path.insert(0, "src")
from fastmcp import Client  # noqa: E402

from line_desktop_mcp.server import mcp  # noqa: E402


async def main() -> None:
    async with Client(mcp) as c:
        for t in await c.list_tools():
            print(t.name)


asyncio.run(main())
