"""openwork-desktop: run a task through OpenWork Desktop's own server and engine.

The harness drives the same server the desktop app uses (in an OpenWork world sandbox, or any
running OpenWork). Per attempt it:

  1. serves the task's world as a remote MCP server (streamable HTTP);
  2. creates a fresh local workspace            POST  /workspaces/local                 (host token)
  3. configures the model, MCP and permissions  PATCH /workspace/:id/config            (client token)
     then reloads the engine                     POST  /workspace/:id/engine/reload
  4. opens a session and sends the brief         POST  /workspace/:id/opencode/session
                                                 POST  /workspace/:id/opencode/session/:sid/prompt_async
  5. waits for the session to go idle            GET   /workspace/:id/opencode/session/status
     (aborts on budget)                          POST  /workspace/:id/opencode/session/:sid/abort
  6. reads messages, including sub-agent sessions, for tokens and cost
                                                 GET   /workspace/:id/opencode/session/:sid/message
                                                 GET   /workspace/:id/opencode/session/:sid/children
Routes as of different-ai/openwork dev@915207cb (apps/server/src/server.ts, routes/workspaces.ts,
routes/operations.ts). Grading reads the MCP world's final state, exactly like every other harness.

Local file, shell and web tools are denied in the workspace so the agent works only through the
company tools, the same surface every other subject gets, and cannot read benchmark files.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from ..mcp_server import SERVER_NAME, HttpWorldServer
from ..providers.base import Usage, read_secret
from ..providers.openai_provider import openrouter_extra_body
from ..tasks import TaskBundle
from ..world import World
from .base import Agent, AgentOutcome, work_context

DENY_LOCAL_TOOLS = {"edit": "deny", "bash": "deny", "webfetch": "deny", "external_directory": "deny"}


class OpenWorkError(RuntimeError):
    pass


class OpenWorkClient:
    def __init__(
        self, base_url: str, token: str | None = None, host_token: str | None = None, timeout: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.host_token = host_token
        self.timeout = timeout

    def request(self, method: str, path: str, body: Any = None, host: bool = False) -> Any:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if host and self.host_token:
            headers["X-OpenWork-Host-Token"] = self.host_token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode(errors="replace")
            raise OpenWorkError(f"{method} {path} -> HTTP {e.code}: {detail}") from e
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode(errors="replace")

    @staticmethod
    def _q(v: str) -> str:
        return urllib.request.quote(v, safe="")

    def create_workspace(self, folder: str, name: str) -> dict[str, Any]:
        out = self.request(
            "POST", "/workspaces/local", {"folderPath": folder, "name": name, "preset": "starter"}, host=True
        )
        ws = out.get("workspace", out) if isinstance(out, dict) else {}
        if not ws.get("id"):
            raise OpenWorkError(f"workspace creation returned no id: {str(out)[:200]}")
        return ws

    def patch_config(self, ws: str, opencode: dict[str, Any]) -> Any:
        return self.request("PATCH", f"/workspace/{self._q(ws)}/config", {"opencode": opencode})

    def reload_engine(self, ws: str) -> Any:
        return self.request("POST", f"/workspace/{self._q(ws)}/engine/reload", {})

    def create_session(self, ws: str, title: str) -> str:
        out = self.request("POST", f"/workspace/{self._q(ws)}/opencode/session", {"title": title})
        sid = (out or {}).get("id") if isinstance(out, dict) else None
        if not sid:
            raise OpenWorkError(f"session creation returned no id: {str(out)[:200]}")
        return sid

    def prompt_async(self, ws: str, sid: str, text: str, model: dict[str, str] | None) -> None:
        body: dict[str, Any] = {
            "messageID": f"msg_owb_{uuid.uuid4().hex[:20]}",
            "parts": [{"type": "text", "text": text}],
        }
        if model:
            body["model"] = model
        self.request("POST", f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/prompt_async", body)

    def status(self, ws: str) -> dict[str, Any]:
        out = self.request("GET", f"/workspace/{self._q(ws)}/opencode/session/status")
        return out if isinstance(out, dict) else {}

    def messages(self, ws: str, sid: str) -> list[dict[str, Any]]:
        out = self.request("GET", f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/message")
        return out if isinstance(out, list) else []

    def children(self, ws: str, sid: str) -> list[dict[str, Any]]:
        try:
            out = self.request("GET", f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/children")
        except OpenWorkError:
            return []
        return out if isinstance(out, list) else []

    def abort(self, ws: str, sid: str) -> None:
        try:
            self.request("POST", f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/abort", {})
        except OpenWorkError:
            pass


def opencode_model_config(subject: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The OpenCode `provider` block for a subject, and its provider id."""
    route, label = subject["model"], subject.get("label", subject["model"])
    default_env = "ANTHROPIC_API_KEY" if subject.get("provider") == "anthropic" else "OPENROUTER_API_KEY"
    key = read_secret(subject.get("api_key_env", default_env)) or ""
    base_url = str(subject.get("base_url", ""))
    if subject.get("provider") == "anthropic":
        return "anthropic", {"anthropic": {"options": {"apiKey": key}, "models": {route: {"name": label}}}}
    if "openrouter.ai" in base_url:
        routing = openrouter_extra_body(subject)
        return "openrouter", {
            "openrouter": {"options": {"apiKey": key}, "models": {route: {"name": label, "options": routing}}}
        }
    return "owb", {
        "owb": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "OpenWork Bench",
            "options": {"baseURL": base_url, "apiKey": key},
            "models": {route: {"name": label}},
        }
    }


def _sum_messages(msgs: list[dict[str, Any]]) -> tuple[Usage, float, int, list[str], str]:
    usage, cost, turns, models, last_text = Usage(), 0.0, 0, [], ""
    for m in msgs:
        info = m.get("info", m)
        if info.get("role") != "assistant":
            continue
        turns += 1
        t = info.get("tokens") or {}
        cache = t.get("cache") or {}
        usage.input_tokens += int(t.get("input", 0) or 0)
        usage.output_tokens += int(t.get("output", 0) or 0) + int(t.get("reasoning", 0) or 0)
        usage.cache_read_tokens += int(cache.get("read", 0) or 0)
        usage.cache_write_tokens += int(cache.get("write", 0) or 0)
        cost += float(info.get("cost", 0) or 0)
        mid = "/".join(x for x in (info.get("providerID"), info.get("modelID")) if x)
        if mid and mid not in models:
            models.append(mid)
        texts = [p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text" and p.get("text")]
        if texts:
            last_text = texts[-1]
    return usage, cost, turns, models, last_text


def _compact(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transcript for the run log: roles, text and tool calls, without engine internals."""
    out = []
    for m in msgs:
        info = m.get("info", m)
        parts = []
        for p in m.get("parts", []):
            if p.get("type") == "text":
                parts.append({"type": "text", "text": p.get("text", "")[:4000]})
            elif p.get("type") == "tool":
                st = p.get("state") or {}
                parts.append(
                    {
                        "type": "tool",
                        "tool": p.get("tool"),
                        "input": st.get("input"),
                        "status": st.get("status"),
                    }
                )
        out.append({"role": info.get("role"), "model": info.get("modelID"), "parts": parts})
    return out


class OpenWorkDesktopAgent(Agent):
    def __init__(self, subject: dict[str, Any], client: OpenWorkClient | None = None):
        super().__init__(subject)
        ow = subject.get("openwork") or {}
        self.cfg = ow
        if client is None and (ow.get("cdp_url") or os.environ.get("OPENWORK_CDP_URL")):
            # Ask the running desktop for its embedded server address and owner token over the
            # debug port, the same way OpenWork's own evals reach it. The token stays in memory.
            from .openwork_connect import server_info

            info = server_info(ow.get("cdp_url") or os.environ["OPENWORK_CDP_URL"])
            client = OpenWorkClient(info["baseUrl"], token=info["token"])
        self.client = client or OpenWorkClient(
            ow.get("url") or os.environ.get("OPENWORK_URL", "http://127.0.0.1:8787"),
            token=read_secret(ow.get("token_env", "OPENWORK_TOKEN")),
            host_token=read_secret(ow.get("host_token_env", "OPENWORK_HOST_TOKEN")),
        )

    def _workspace(self, bundle: TaskBundle, repeat: int) -> str:
        if self.cfg.get("workspace_id"):
            return self.cfg["workspace_id"]
        root = Path(self.cfg.get("workspace_root", "/tmp/owb-workspaces"))
        folder = root / f"{self.subject['id'].replace('@', '_')}-{bundle.id}-r{repeat}-{uuid.uuid4().hex[:6]}"
        return self.client.create_workspace(str(folder), f"OWB {bundle.id} r{repeat}")["id"]

    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        budgets = bundle.task.budgets
        poll = float(self.cfg.get("poll_s", 2.0))
        grace = float(self.cfg.get("start_grace_s", 20.0))
        ws = sid = None
        meta: dict[str, Any] = {"harness": "openwork-desktop"}
        try:
            with HttpWorldServer(
                bundle,
                world=world,
                host=self.cfg.get("mcp_host", "127.0.0.1"),
                advertise_host=self.cfg.get("mcp_advertise_host"),
            ) as srv:
                ws = self._workspace(bundle, repeat)
                provider_id, provider_block = opencode_model_config(self.subject)
                self.client.patch_config(
                    ws,
                    {
                        "provider": provider_block,
                        "model": f"{provider_id}/{self.subject['model']}",
                        "mcp": {
                            SERVER_NAME: {"type": "remote", "url": srv.url, "enabled": True, "oauth": False}
                        },
                        "permission": dict(DENY_LOCAL_TOOLS),
                    },
                )
                self.client.reload_engine(ws)
                sid = self.client.create_session(ws, f"OpenWork Bench · {bundle.id} · r{repeat}")
                meta.update(workspace_id=ws, session_id=sid, mcp_url=srv.url)
                started = time.monotonic()
                self.client.prompt_async(
                    ws,
                    sid,
                    f"{work_context(world)}\n\n---\n\n{bundle.task.brief}",
                    {"providerID": provider_id, "modelID": self.subject["model"]},
                )
                status, seen_busy = "completed", False
                while True:
                    time.sleep(poll)
                    elapsed = time.monotonic() - started
                    st = (self.client.status(ws) or {}).get(sid) or {}
                    busy = st.get("type") in ("busy", "retry")
                    seen_busy = seen_busy or busy
                    if len(world.actions) >= budgets.max_steps:
                        status = "budget_steps"
                        self.client.abort(ws, sid)
                        break
                    if elapsed > budgets.timeout_s:
                        status = "timeout"
                        self.client.abort(ws, sid)
                        break
                    if not busy and (seen_busy or elapsed > grace or world.done):
                        break
                msgs = self.client.messages(ws, sid)
                for child in self.client.children(ws, sid):
                    if child.get("id"):
                        msgs += self.client.messages(ws, child["id"])
        except Exception as e:  # infrastructure failures are recorded and excluded from scoring
            return AgentOutcome(
                status="error", steps=len(world.actions), error=f"{type(e).__name__}: {e}"[:500], meta=meta
            )

        usage, cost, turns, models, last_text = _sum_messages(msgs)
        if usage.total >= budgets.max_tokens and status == "completed":
            status = "budget_tokens"
        if world.answer is None:
            world.answer = last_text
            if status == "completed":
                status = "no_submit"
        if any("error" in (m.get("info", m) or {}) for m in msgs) and turns == 0:
            status = "error"
        return AgentOutcome(
            status=status,
            usage=usage,
            steps=len(world.actions),
            turns=turns,
            transcript=_compact(msgs),
            billed_usd=cost if cost > 0 else None,
            served_by=models,
            meta=meta,
        )
