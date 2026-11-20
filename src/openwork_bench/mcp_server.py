"""Serve one task's world as an MCP server, over stdio or streamable HTTP.

This is how agent products (OpenWork Desktop, Claude Code, Codex, ...) take a task. OpenWork
attaches it as a remote MCP server in the workspace config:

    owb world serve vendor-shortlist --http --port 8765 --state-out state.json
    # opencode config: {"mcp": {"owb-world": {"type": "remote", "url": "http://127.0.0.1:8765/mcp"}}}
    owb grade-state vendor-shortlist state.json

Requires the `mcp` extra (MCP Python SDK 2.x).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

from .tasks import TaskBundle
from .world import World

SERVER_NAME = "owb-world"


def _build_server(world: World, bundle: TaskBundle, on_change=None):
    import mcp.types as types
    from mcp.server.lowlevel import Server

    async def on_list_tools(ctx, params):  # noqa: ARG001
        return types.ListToolsResult(
            tools=[
                types.Tool(name=t.name, description=t.description, input_schema=t.parameters)
                for t in world.tool_specs()
            ]
        )

    async def on_call_tool(ctx, params):  # noqa: ARG001
        ok, text = world.call(params.name, dict(params.arguments or {}))
        if on_change:
            on_change()
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=not ok)

    return Server(
        SERVER_NAME,
        version="0.1.0",
        instructions=(
            "Company workplace tools for this task: email, calendar, drive (company files), CRM, team chat "
            "and directory. 'Drive' always means these drive_* tools, not the local disk. "
            "Call submit with the final answer when done."
        ),
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def _saver(world: World, state_out: Path | None):
    def save() -> None:
        if state_out:
            Path(state_out).write_text(json.dumps(world.snapshot(), indent=1, default=str))

    return save


def serve(bundle: TaskBundle, state_out: Path | None = None) -> None:
    """Blocking stdio server."""
    import anyio
    from mcp.server.stdio import stdio_server

    world = World(bundle.world, bundle.workspace)
    save = _saver(world, state_out)
    server = _build_server(world, bundle, on_change=save)

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    save()
    anyio.run(main)


def free_port(host: str = "127.0.0.1") -> int:
    with socket.socket() as s:
        s.bind((host, 0))
        return s.getsockname()[1]


class HttpWorldServer:
    """A task world served over streamable HTTP in a background thread.

    with HttpWorldServer(bundle) as srv:
        ... point an agent at srv.url ...
        snapshot = srv.world.snapshot()
    """

    def __init__(
        self,
        bundle: TaskBundle,
        host: str = "127.0.0.1",
        port: int | None = None,
        state_out: Path | None = None,
        world: World | None = None,
        advertise_host: str | None = None,
    ):
        self.bundle = bundle
        self.host = host
        self.port = port or free_port(host)
        self.world = world or World(bundle.world, bundle.workspace)
        self.advertise_host = advertise_host
        self.state_out = state_out
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.advertise_host or self.host}:{self.port}/mcp"

    def __enter__(self) -> HttpWorldServer:
        import uvicorn

        save = _saver(self.world, self.state_out)
        app = _build_server(self.world, self.bundle, on_change=save).streamable_http_app(
            stateless_http=True, host=self.host
        )
        cfg = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning", lifespan="on")
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, daemon=True, name=f"owb-world-{self.port}")
        self._thread.start()
        deadline = time.monotonic() + 10
        while not getattr(self._server, "started", False):
            if time.monotonic() > deadline:
                raise RuntimeError("world MCP server did not start")
            time.sleep(0.05)
        save()
        return self

    def __exit__(self, *exc) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=10)


def serve_http(bundle: TaskBundle, host: str, port: int, state_out: Path | None = None) -> None:
    """Blocking HTTP server (Ctrl-C to stop)."""
    with HttpWorldServer(bundle, host=host, port=port, state_out=state_out) as srv:
        print(f"OpenWork Bench world for {bundle.id} at {srv.url}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
