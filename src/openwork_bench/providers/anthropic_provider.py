"""Claude via the official Anthropic Python SDK.

Credentials resolve the SDK's usual way: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
`ant auth login` profile. Server-side refusal fallbacks are deliberately NOT enabled: a
benchmark must measure the named model, so a refusal is recorded as a refusal.
"""

from __future__ import annotations

from typing import Any

from .base import Conversation, ModelReply, ToolCall, Usage


def _dump(block: Any) -> dict[str, Any]:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    if isinstance(block, dict):
        return block
    return dict(vars(block))


class AnthropicConversation(Conversation):
    def __init__(self, cfg: dict[str, Any], system: str, tools: list[dict[str, Any]], client: Any = None):
        super().__init__(cfg=cfg, system=system, tools=tools)
        if client is None:
            import anthropic

            client = anthropic.Anthropic(max_retries=int(cfg.get("max_retries", 4)))
        self.client = client
        self.messages: list[dict[str, Any]] = []

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self.transcript.append({"role": "user", "content": text})

    def call(self) -> ModelReply:
        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "max_tokens": int(self.cfg.get("max_output_tokens", 16000)),
            "system": self.system,
            "messages": self.messages,
        }
        if self.tools:
            kwargs["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                for t in self.tools
            ]
        if self.cfg.get("effort"):
            kwargs["output_config"] = {"effort": self.cfg["effort"]}
        resp = self.client.messages.create(**kwargs)

        content = list(resp.content)
        self.messages.append({"role": "assistant", "content": content})
        dumped = [_dump(b) for b in content]
        self.transcript.append({"role": "assistant", "content": dumped, "stop_reason": resp.stop_reason})

        text = "\n".join(b.text for b in content if getattr(b, "type", None) == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, args=dict(b.input or {}))
            for b in content
            if getattr(b, "type", None) == "tool_use"
        ]
        u = resp.usage
        usage = Usage(
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        )
        return ModelReply(
            text=text, tool_calls=calls, usage=usage, stop_reason=str(resp.stop_reason), raw=resp
        )

    def add_tool_results(self, results: list[tuple[ToolCall, bool, str]]) -> None:
        blocks = [
            {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": text,
                **({} if ok else {"is_error": True}),
            }
            for call, ok, text in results
        ]
        # All results for one assistant turn go back in a single user message.
        self.messages.append({"role": "user", "content": blocks})
        self.transcript.append({"role": "user", "content": blocks})
