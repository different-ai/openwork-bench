"""The world MCP server works with a real MCP client over stdio."""

import json
import sys

import pytest

mcp = pytest.importorskip("mcp")


def test_world_over_mcp(tmp_path):
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from conftest import ROOT

    state = tmp_path / "state.json"
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "openwork_bench.cli",
            "--tasks-dir",
            str(ROOT / "tasks"),
            "world",
            "serve",
            "expense-policy-answer",
            "--state-out",
            str(state),
        ],
    )

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                assert {"mail_send", "drive_read", "submit"} <= names
                res = await session.call_tool(
                    "drive_read", {"path": "/policies/travel-and-expense-policy-2025.md"}
                )
                assert "Alcohol" in res.content[0].text
                await session.call_tool("submit", {"answer": "hi"})

    anyio.run(go)
    snap = json.loads(state.read_text())
    assert snap["answer"] == "hi" and snap["actions"][0]["tool"] == "drive_read"
