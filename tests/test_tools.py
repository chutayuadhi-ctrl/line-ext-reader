"""line-ext-reader tool-surface tests (LineClient is mocked; no browser)."""

import asyncio
import os
import unittest
from unittest.mock import patch

from line_ext_msg import LoginRequired, Room, StepResult

from line_desktop_mcp.tools import line_msg as lm

EXPECTED_TOOLS = {"line_status", "list_rooms", "get_messages", "unread_digest", "search_messages"}


def _rooms() -> list[Room]:
    return [
        Room(index=0, id="mid-family", name="ครอบครัว", unread=3, last_preview="กินข้าวยัง", last_time="8:13 AM"),
        Room(index=1, id="mid-work", name="งาน", unread=0, last_preview="ส่งไฟล์แล้ว", last_time="9:00 AM"),
    ]


class FakeClient:
    seen_calls: list = []
    messages_calls: list = []
    _steps: list = []
    _error: Exception | None = None

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def status(self, **kwargs):
        FakeClient.seen_calls.append(kwargs)
        if FakeClient._error is not None:
            raise FakeClient._error
        return FakeClient._steps

    def get_messages(self, **kwargs):
        FakeClient.messages_calls.append(kwargs)
        return []


class ResolveTest(unittest.TestCase):
    def test_by_index_id_name(self):
        self.assertEqual(lm._resolve_ref(1, _rooms()).id, "mid-work")
        self.assertEqual(lm._resolve_ref("mid-family", _rooms()).index, 0)
        self.assertEqual(lm._resolve_ref("ครอบ", _rooms()).id, "mid-family")

    def test_bad_ref_becomes_entry(self):
        targets, skipped = lm._resolve_targets(["งาน", "ไม่มีห้องนี้"], _rooms())
        self.assertEqual([r.id for r in targets], ["mid-work"])
        self.assertEqual(skipped[0]["error"], "RoomNotFound")


class EnvelopeTest(unittest.TestCase):
    def test_fail_carries_next_hint(self):
        out = lm._fail(LoginRequired("x"))
        self.assertFalse(out["ok"])
        self.assertIn("next", out)


class StatusTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeClient._steps = [StepResult(name="Logged in", passed=True, detail="ok")]
        FakeClient._error = None
        FakeClient.seen_calls = []
        FakeClient.messages_calls = []

    async def _call(self, name, args):
        from fastmcp import Client

        from line_desktop_mcp.server import mcp

        with patch.object(lm, "LineClient", FakeClient):
            async with Client(mcp) as client:
                return await client.call_tool(name, args)

    async def test_waits_for_login_by_default(self):
        await self._call("line_status", {})
        self.assertEqual(FakeClient.seen_calls, [{"wait_for_login": True, "login_timeout_ms": 180000}])

    async def test_include_media_maps_to_with_media(self):
        await self._call("get_messages", {"include_media": True})
        self.assertTrue(FakeClient.messages_calls[0]["with_media"])


class LibraryEnvTest(unittest.TestCase):
    KEYS = ("LINE_EXT_MSG_PROFILE", "LINE_EXT_MSG_PORT", "LINE_EXT_MSG_DIALOG_TITLE")

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self.KEYS}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_defaults_are_mac_paths(self):
        from line_desktop_mcp import server

        for k in self.KEYS:
            os.environ.pop(k, None)
        server._configure_library()
        self.assertEqual(os.environ["LINE_EXT_MSG_PROFILE"], "~/Library/Application Support/line-ext-reader")
        self.assertEqual(os.environ["LINE_EXT_MSG_PORT"], "9223")

    def test_existing_values_are_preserved(self):
        from line_desktop_mcp import server

        os.environ["LINE_EXT_MSG_PORT"] = "9999"
        server._configure_library()
        self.assertEqual(os.environ["LINE_EXT_MSG_PORT"], "9999")


class ToolSurfaceTest(unittest.IsolatedAsyncioTestCase):
    """(ค) the tool list is exactly the 5 read tools (A3)."""

    async def test_exactly_five_read_tools(self):
        from fastmcp import Client

        from line_desktop_mcp.server import mcp

        async with Client(mcp) as client:
            names = {t.name for t in await client.list_tools()}
        self.assertEqual(names, EXPECTED_TOOLS)
        for banned in ("clear_session", "probe_session", "unread_full", "send_message"):
            self.assertNotIn(banned, names)

    def test_all_tools_are_read_only_hinted(self):
        from line_desktop_mcp.server import mcp

        for name in EXPECTED_TOOLS:
            tool = asyncio.run(mcp.get_tool(name))
            self.assertTrue(tool.annotations.read_only_hint, name)
            self.assertFalse(tool.annotations.destructive_hint or False, name)


class TransportTest(unittest.TestCase):
    def test_stdio_only(self):
        from line_desktop_mcp import cli

        self.assertFalse(hasattr(cli, "build_parser"))
        src = open(cli.__file__, encoding="utf-8").read()
        self.assertIn('transport="stdio"', src)
        self.assertNotIn('"http"', src)


if __name__ == "__main__":
    unittest.main()
