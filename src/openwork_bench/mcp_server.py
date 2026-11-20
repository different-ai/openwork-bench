"""Serve one task's world as an MCP server over stdio.

This is how external agent products (OpenWork, Claude Code, Codex, Cursor, ...) take a task:
point the product at this server, give it the brief, and when it stops, grade the saved state:

    owb world serve vendor-shortlist --state-out state.json      # MCP over stdio
    owb grade-state vendor-shortlist state.json

Requires the `mcp` extra (MCP Python SDK 2.x).
"""

from __future__ import annotations

import json
from pathlib import Path

from .tasks import TaskBundle
from .world import World


def serve(bundle: TaskBundle, state_out: Path | None = None) -> None:
    import anyio
    import mcp.types as types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server

    world = World(bundle.world, bundle.workspace)

    def save() -> None:
        if state_out:
            Path(state_out).write_text(json.dumps(world.snapshot(), indent=1, default=str))

    async def on_list_tools(ctx, params):  # noqa: ARG001
        return types.ListToolsResult(
            tools=[
                types.Tool(name=t.name, description=t.description, input_schema=t.parameters)
                for t in world.tool_specs()
            ]
        )

    async def on_call_tool(ctx, params):  # noqa: ARG001
        ok, text = world.call(params.name, dict(params.arguments or {}))
        save()
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=not ok)

    server = Server(
        "openwork-bench-world",
        version="0.1.0",
        instructions=f"Workplace tools for OpenWork Bench task {bundle.id}. Task brief:\n{bundle.task.brief}",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    save()
    anyio.run(main)
