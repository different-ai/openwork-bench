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
        self.v2 = False  # set once the server says the history belongs to engine v2

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
        # The server answers with the full registry: {"activeId": ..., "workspaces": [...]}.
        # Older shapes returned {"workspace": {...}} or the workspace itself.
        ws: dict[str, Any] = {}
        if isinstance(out, dict):
            if isinstance(out.get("workspaces"), list):
                items = [w for w in out["workspaces"] if isinstance(w, dict)]
                ws = next((w for w in items if w.get("path") == folder), None) or next(
                    (w for w in items if w.get("id") == out.get("activeId")), {}
                )
            else:
                ws = out.get("workspace", out)
        if not ws.get("id"):
            raise OpenWorkError(f"workspace creation returned no id: {str(out)[:200]}")
        return ws

    def patch_config(self, ws: str, opencode: dict[str, Any]) -> Any:
        return self.request("PATCH", f"/workspace/{self._q(ws)}/config", {"opencode": opencode})

    def reload_engine(self, ws: str) -> Any:
        return self.request("POST", f"/workspace/{self._q(ws)}/engine/reload", {})

    def create_session(self, ws: str, title: str, model: dict[str, str] | None = None) -> str:
        """Open a session. A desktop whose history belongs to engine v2 refuses v1 writes
        (409 engine_v1_history_adopted); those go to the native v2 routes, like the app's own."""
        if not self.v2:
            try:
                out = self.request("POST", f"/workspace/{self._q(ws)}/opencode/session", {"title": title})
            except OpenWorkError as e:
                if "engine_v1_history_adopted" not in str(e):
                    raise
                self.v2 = True
            else:
                sid = (out or {}).get("id") if isinstance(out, dict) else None
                if not sid:
                    raise OpenWorkError(f"session creation returned no id: {str(out)[:200]}")
                return sid
        body: dict[str, Any] = {"title": title}
        if model:
            body["model"] = {"providerID": model["providerID"], "id": model["modelID"]}
        out = self.request("POST", f"/workspace/{self._q(ws)}/opencode2/api/session", body)
        row = out.get("data", out) if isinstance(out, dict) else {}
        info = row.get("info", row) if isinstance(row, dict) else {}
        if not isinstance(info, dict) or not info.get("id"):
            raise OpenWorkError(f"v2 session creation returned no id: {str(out)[:200]}")
        return info["id"]

    def prompt_async(self, ws: str, sid: str, text: str, model: dict[str, str] | None) -> None:
        message_id = f"msg_owb_{uuid.uuid4().hex[:20]}"
        if self.v2:
            base = f"/workspace/{self._q(ws)}/opencode2/api/session/{self._q(sid)}"
            if model:
                self.request(
                    "POST",
                    f"{base}/model",
                    {"model": {"providerID": model["providerID"], "id": model["modelID"]}},
                )
            self.request("POST", f"{base}/prompt", {"text": text, "id": message_id, "delivery": "steer"})
            return
        body: dict[str, Any] = {"messageID": message_id, "parts": [{"type": "text", "text": text}]}
        if model:
            body["model"] = model
        self.request("POST", f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/prompt_async", body)

    def detect_v2(self) -> bool:
        """True when the desktop routes chats to engine v2 (the default for fresh installs)."""
        try:
            st = self.request("GET", "/experimental/engine-v2-preview/status")
        except OpenWorkError:
            return self.v2
        self.v2 = bool(isinstance(st, dict) and st.get("enabled") and st.get("chatRouting"))
        return self.v2

    def save_provider_key(self, ws: str, provider_id: str, key: str) -> None:
        """Save an API key the way the app's AI Providers page does (OpenCode auth.set).
        On engine v2, OpenWork mirrors it into v2's native provider."""
        self.request(
            "PUT",
            f"/workspace/{self._q(ws)}/opencode/auth/{self._q(provider_id)}",
            {"type": "api", "key": key},
        )

    def session_v2(self, ws: str, sid: str) -> dict[str, Any]:
        out = self.request("GET", f"/workspace/{self._q(ws)}/opencode2/api/session/{self._q(sid)}")
        return out.get("data", out) if isinstance(out, dict) else {}

    def messages_v2(self, ws: str, sid: str) -> list[dict[str, Any]]:
        out = self.request(
            "GET", f"/workspace/{self._q(ws)}/opencode2/api/session/{self._q(sid)}/message?order=asc"
        )
        data = out.get("data", out) if isinstance(out, dict) else out
        return data if isinstance(data, list) else []

    def status(self, ws: str) -> dict[str, Any]:
        if self.v2:
            out = self.request("GET", f"/workspace/{self._q(ws)}/opencode2/api/session/active")
            active = out.get("data", out) if isinstance(out, dict) else {}
            return {
                sid: {"type": "busy" if (v or {}).get("type") == "running" else "idle"}
                for sid, v in (active or {}).items()
            }
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
        paths = [f"/workspace/{self._q(ws)}/opencode/session/{self._q(sid)}/abort"]
        if self.v2:
            paths.insert(0, f"/workspace/{self._q(ws)}/opencode2/api/session/{self._q(sid)}/abort")
        for path in paths:
            try:
                self.request("POST", path, {})
                return
            except OpenWorkError:
                continue


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

    _keys_saved: set[str] = set()

    @staticmethod
    def _outcome_v2(world, budgets, status, info, msgs, meta) -> AgentOutcome:
        t = info.get("tokens") or {}
        cache = t.get("cache") or {}
        usage = Usage(
            input_tokens=int(t.get("input", 0) or 0),
            output_tokens=int(t.get("output", 0) or 0) + int(t.get("reasoning", 0) or 0),
            cache_read_tokens=int(cache.get("read", 0) or 0),
            cache_write_tokens=int(cache.get("write", 0) or 0),
        )
        cost = float(info.get("cost", 0) or 0)
        model = info.get("model") or {}
        served = [f"{model.get('providerID')}/{model.get('id')}"] if model.get("id") else []
        meta["outcome"] = info.get("outcome")
        if usage.total == 0 and not world.actions:
            status = "error"  # the model never ran: provider or engine failure, not a score
        elif usage.total >= budgets.max_tokens and status == "completed":
            status = "budget_tokens"
        if world.answer is None:
            texts = [
                m.get("text")
                for m in msgs
                if isinstance(m, dict) and m.get("text") and m.get("role", m.get("type")) != "user"
            ]
            world.answer = texts[-1] if texts else ""
            if status == "completed":
                status = "no_submit"
        transcript = [
            {k: (v[:4000] if isinstance(v, str) else v) for k, v in m.items()}
            for m in msgs
            if isinstance(m, dict)
        ][:200]
        return AgentOutcome(
            status=status,
            usage=usage,
            steps=len(world.actions),
            turns=sum(1 for m in msgs if isinstance(m, dict) and m.get("role", m.get("type")) == "assistant"),
            transcript=transcript,
            billed_usd=cost if cost > 0 else None,
            served_by=served,
            meta=meta,
            error=None
            if status != "error"
            else f"engine v2 session outcome {info.get('outcome')!r} with no tokens",
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
                v2 = self.client.detect_v2()
                update: dict[str, Any] = {
                    "model": f"{provider_id}/{self.subject['model']}",
                    "mcp": {SERVER_NAME: {"type": "remote", "url": srv.url, "enabled": True, "oauth": False}},
                    "permission": dict(DENY_LOCAL_TOOLS),
                }
                if v2:
                    # Engine v2 cannot map a configured OpenRouter block; it mirrors the native provider
                    # from a saved key instead. Clear any earlier block and save the key once.
                    update["provider"] = {provider_id: None}
                    if provider_id not in self._keys_saved:
                        key = read_secret(self.subject.get("api_key_env", "OPENROUTER_API_KEY")) or ""
                        self.client.save_provider_key(ws, provider_id, key)
                        self._keys_saved.add(provider_id)
                else:
                    update["provider"] = provider_block
                meta["engine"] = "v2" if v2 else "v1"
                self.client.patch_config(ws, update)
                self.client.reload_engine(ws)
                model_ref = {"providerID": provider_id, "modelID": self.subject["model"]}
                sid = self.client.create_session(ws, f"OpenWork Bench · {bundle.id} · r{repeat}", model_ref)
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
                if self.client.v2:
                    info = self.client.session_v2(ws, sid)
                    msgs = self.client.messages_v2(ws, sid)
                    return self._outcome_v2(world, budgets, status, info, msgs, meta)
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
