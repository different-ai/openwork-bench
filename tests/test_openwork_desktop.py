"""The openwork-desktop harness against a fake OpenWork server.

The fake implements the server routes the harness uses and plays the agent: when a prompt
arrives it connects to the task's MCP world over streamable HTTP (the URL the harness put in
the workspace config) and replays the reference solution, like a model would.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("mcp")

from openwork_bench.harness.openwork_desktop import DENY_LOCAL_TOOLS  # noqa: E402
from openwork_bench.runner import run_one  # noqa: E402
from openwork_bench.subjects import load_subjects  # noqa: E402

CLIENT, HOST = "client-secret", "host-secret"


class FakeOpenWork:
    def __init__(self, steps, hang=False, v2=False):
        self.steps, self.hang, self.v2 = steps, hang, v2
        self.config, self.prompts, self.calls, self.busy, self.aborted = {}, [], [], False, False
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=None):
                raw = b"" if body is None else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}")

            def _route(self, method):
                p = self.path
                fake.calls.append((method, p))
                if p == "/workspaces/local":
                    if self.headers.get("X-OpenWork-Host-Token") != HOST:
                        return self._send(401, {"error": "host token"})
                    folder = self._body()["folderPath"]
                    return self._send(
                        200,
                        {
                            "activeId": "ws_1",
                            "workspaces": [
                                {"id": "ws_0", "path": "/other", "workspaceType": "local"},
                                {"id": "ws_1", "path": folder, "workspaceType": "local"},
                            ],
                        },
                    )
                if self.headers.get("Authorization") != f"Bearer {CLIENT}":
                    return self._send(401, {"error": "client token"})
                if method == "PATCH" and p == "/workspace/ws_1/config":
                    fake.config = self._body()["opencode"]
                    return self._send(200, {"ok": True})
                if p == "/workspace/ws_1/engine/reload":
                    return self._send(200, {"ok": True})
                if method == "POST" and p == "/workspace/ws_1/opencode/session":
                    if fake.v2:
                        return self._send(
                            409,
                            {
                                "code": "engine_v1_history_adopted",
                                "message": "This history is owned by OpenCode v2.",
                            },
                        )
                    return self._send(200, {"id": "ses_1"})
                if p == "/experimental/engine-v2-preview/status":
                    return self._send(200, {"enabled": fake.v2, "chatRouting": fake.v2})
                if fake.v2 and method == "PUT" and p == "/workspace/ws_1/opencode/auth/openrouter":
                    fake.saved_key = self._body()
                    return self._send(200, True)
                if fake.v2 and p == "/workspace/ws_1/opencode2/api/session/active":
                    return self._send(200, {"data": {"ses_1": {"type": "running"}} if fake.busy else {}})
                if fake.v2 and method == "GET" and p == "/workspace/ws_1/opencode2/api/session/ses_1":
                    return self._send(
                        200,
                        {
                            "data": {
                                "id": "ses_1",
                                "model": {"providerID": "openrouter", "id": "z-ai/glm-5.3"},
                                "cost": 0.0031,
                                "tokens": {
                                    "input": 2000,
                                    "output": 400,
                                    "reasoning": 100,
                                    "cache": {"read": 0, "write": 0},
                                },
                                "outcome": "completed",
                            }
                        },
                    )
                if fake.v2 and p.startswith("/workspace/ws_1/opencode2/api/session/ses_1/message"):
                    return self._send(
                        200,
                        {
                            "data": [
                                {"id": "m1", "role": "user", "text": "brief"},
                                {"id": "m2", "role": "assistant", "text": "Replied to Jordan."},
                            ]
                        },
                    )
                if fake.v2 and p == "/workspace/ws_1/opencode2/api/session":
                    fake.v2_create = self._body()
                    return self._send(200, {"data": {"info": {"id": "ses_1"}}})
                if fake.v2 and p == "/workspace/ws_1/opencode2/api/session/ses_1/model":
                    fake.v2_model = self._body()
                    return self._send(200, {"ok": True})
                if fake.v2 and p == "/workspace/ws_1/opencode2/api/session/ses_1/prompt":
                    fake.prompts.append(self._body())
                    fake.busy = True
                    threading.Thread(target=fake.play, daemon=True).start()
                    return self._send(200, {"ok": True})
                if p == "/workspace/ws_1/opencode/session/ses_1/prompt_async":
                    fake.prompts.append(self._body())
                    fake.busy = True
                    threading.Thread(target=fake.play, daemon=True).start()
                    return self._send(204)
                if p == "/workspace/ws_1/opencode/session/status":
                    return self._send(200, {"ses_1": {"type": "busy"}} if fake.busy else {})
                if p == "/workspace/ws_1/opencode/session/ses_1/message":
                    return self._send(
                        200,
                        [
                            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "brief"}]},
                            {
                                "info": {
                                    "role": "assistant",
                                    "providerID": "openrouter",
                                    "modelID": "z-ai/glm-5.3",
                                    "tokens": {
                                        "input": 1200,
                                        "output": 300,
                                        "reasoning": 50,
                                        "cache": {"read": 100, "write": 0},
                                    },
                                    "cost": 0.0021,
                                },
                                "parts": [
                                    {
                                        "type": "tool",
                                        "tool": "owb-world_mail_send",
                                        "state": {"status": "completed", "input": {}},
                                    },
                                    {"type": "text", "text": "Replied to Jordan."},
                                ],
                            },
                        ],
                    )
                if p == "/workspace/ws_1/opencode/session/ses_1/children":
                    return self._send(200, [{"id": "ses_child"}])
                if p == "/workspace/ws_1/opencode/session/ses_child/message":
                    return self._send(
                        200,
                        [
                            {
                                "info": {
                                    "role": "assistant",
                                    "providerID": "openrouter",
                                    "modelID": "z-ai/glm-5.3",
                                    "tokens": {"input": 500, "output": 100},
                                    "cost": 0.0005,
                                },
                                "parts": [],
                            }
                        ],
                    )
                if p == "/workspace/ws_1/opencode/session/ses_1/abort":
                    fake.aborted, fake.busy = True, False
                    return self._send(200, True)
                return self._send(404, {"error": p})

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PATCH(self):
                self._route("PATCH")

            def do_PUT(self):
                self._route("PUT")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def play(self):
        """Act as the agent: call the task's tools through the MCP world the harness attached."""
        if self.hang:
            return
        import anyio
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        url = self.config["mcp"]["owb-world"]["url"]

        async def go():
            async with streamable_http_client(url) as streams:
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as s:
                    await s.initialize()
                    for step in self.steps:
                        await s.call_tool(step["tool"], step.get("args", {}))

        anyio.run(go)
        self.busy = False


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("OPENWORK_TOKEN", CLIENT)
    monkeypatch.setenv("OPENWORK_HOST_TOKEN", HOST)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")


def _subject(url, **ow):
    s = dict(load_subjects()["glm-5.3@openwork-desktop"])
    s["openwork"] = {
        "url": url,
        "poll_s": 0.05,
        "start_grace_s": 3,
        "workspace_root": "/tmp/owb-test-ws",
        **ow,
    }
    return s


def test_runs_a_task_through_openwork_and_grades_the_world(env, by_id):
    b = by_id["expense-policy-answer"]
    fake = FakeOpenWork(b.reference)
    row, traj = run_one(
        _subject(fake.url),
        b,
        1,
        "run-test",
        "v0.1",
        scoring=None or __import__("openwork_bench.grading", fromlist=["ScoringConfig"]).ScoringConfig(),
    )

    assert row["status"] == "completed" and row["score"] == 1.0 and row["success"]
    # cost and tokens include the sub-agent session
    assert row["cost_usd"] == pytest.approx(0.0026) and row["cost_source"] == "billed"
    assert row["usage"]["input_tokens"] == 1700 and row["usage"]["output_tokens"] == 450
    assert row["served_by"] == ["openrouter/z-ai/glm-5.3"]
    assert row["open_weights_revision"]

    cfg = fake.config
    assert cfg["model"] == "openrouter/z-ai/glm-5.3"
    routing = cfg["provider"]["openrouter"]["models"]["z-ai/glm-5.3"]["options"]["provider"]
    assert routing["allow_fallbacks"] is False and routing["quantizations"] == ["bf16", "fp8"]
    assert cfg["mcp"]["owb-world"]["type"] == "remote"
    assert cfg["permission"] == DENY_LOCAL_TOOLS
    prompt = fake.prompts[0]
    assert prompt["model"] == {"providerID": "openrouter", "modelID": "z-ai/glm-5.3"}
    assert "Reply to Jordan" in prompt["parts"][0]["text"] and "Sam Rivera" in prompt["parts"][0]["text"]
    assert traj["transcript"][1]["parts"][0]["tool"] == "owb-world_mail_send"


def test_timeout_aborts_the_session(env, by_id):
    from openwork_bench.grading import ScoringConfig

    b = by_id["vendor-shortlist"]
    short = b.task.model_copy(update={"budgets": b.task.budgets.model_copy(update={"timeout_s": 1})})
    bundle = type(b)(task=short, world=b.world, workspace=b.workspace, reference=b.reference, path=b.path)
    fake = FakeOpenWork(b.reference, hang=True)
    row, _ = run_one(_subject(fake.url), bundle, 1, "run-test", "v0.1", scoring=ScoringConfig())
    assert row["status"] == "timeout" and fake.aborted and row["score"] == 0.0


def test_server_errors_are_infrastructure_errors(env, by_id):
    from openwork_bench.grading import ScoringConfig

    b = by_id["vendor-shortlist"]
    row, _ = run_one(_subject("http://127.0.0.1:9"), b, 1, "run-test", "v0.1", scoring=ScoringConfig())
    assert row["status"] == "error" and row["error"]


def test_v2_desktop_uses_native_session_routes(env, by_id):
    from openwork_bench.grading import ScoringConfig
    from openwork_bench.harness import openwork_desktop

    openwork_desktop._SAVED_KEYS.clear()

    b = by_id["expense-policy-answer"]
    fake = FakeOpenWork(b.reference, v2=True)
    row, _ = run_one(_subject(fake.url), b, 1, "run-test", "v0.1", scoring=ScoringConfig())
    assert row["status"] == "completed" and row["score"] == 1.0
    assert fake.v2_create["model"] == {"providerID": "openrouter", "id": "z-ai/glm-5.3"}
    assert fake.v2_model == {"model": {"providerID": "openrouter", "id": "z-ai/glm-5.3"}}
    assert fake.prompts[0]["delivery"] == "steer" and "Reply to Jordan" in fake.prompts[0]["text"]
    assert fake.saved_key == {"type": "api", "key": "test-key"}
    assert fake.config["provider"] == {"openrouter": None}  # v2 mirrors the native provider instead
    assert row["cost_usd"] == pytest.approx(0.0031) and row["usage"]["output_tokens"] == 500
    assert row["served_by"] == ["openrouter/z-ai/glm-5.3"]
