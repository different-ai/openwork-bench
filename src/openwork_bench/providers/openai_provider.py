"""Any OpenAI-compatible Chat Completions endpoint (OpenAI, OpenRouter, vLLM, Ollama, ...)."""

from __future__ import annotations

import json
import os
from typing import Any

from .base import Conversation, ModelReply, ToolCall, Usage


class OpenAIConversation(Conversation):
    def __init__(self, cfg: dict[str, Any], system: str, tools: list[dict[str, Any]], client: Any = None):
        super().__init__(cfg=cfg, system=system, tools=tools)
        if client is None:
            from openai import OpenAI

            key_env = cfg.get("api_key_env", "OPENAI_API_KEY")
            client = OpenAI(
                api_key=os.environ.get(key_env),
                base_url=cfg.get("base_url") or None,
                max_retries=int(cfg.get("max_retries", 4)),
            )
        self.client = client
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        self.transcript.append({"role": "system", "content": system})

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self.transcript.append({"role": "user", "content": text})

    def call(self) -> ModelReply:
        kwargs: dict[str, Any] = {"model": self.cfg["model"], "messages": self.messages}
        if self.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in self.tools
            ]
        if self.cfg.get("max_output_tokens"):
            kwargs[self.cfg.get("max_tokens_param", "max_completion_tokens")] = int(
                self.cfg["max_output_tokens"]
            )
        if self.cfg.get("reasoning_effort"):
            kwargs["reasoning_effort"] = self.cfg["reasoning_effort"]
        kwargs.update(self.cfg.get("extra_params", {}))
        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = list(getattr(msg, "tool_calls", None) or [])
        assistant: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            assistant["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        self.messages.append(assistant)
        self.transcript.append({**assistant, "finish_reason": choice.finish_reason})

        calls = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__invalid_json__": tc.function.arguments}
            calls.append(
                ToolCall(id=tc.id, name=tc.function.name, args=args if isinstance(args, dict) else {})
            )
        u = getattr(resp, "usage", None)
        cached = 0
        details = getattr(u, "prompt_tokens_details", None)
        if details is not None:
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        usage = Usage(
            input_tokens=int(getattr(u, "prompt_tokens", 0) or 0) - cached,
            output_tokens=int(getattr(u, "completion_tokens", 0) or 0),
            cache_read_tokens=cached,
        )
        stop = (
            "tool_use"
            if calls
            else ("refusal" if getattr(msg, "refusal", None) else str(choice.finish_reason))
        )
        return ModelReply(text=msg.content or "", tool_calls=calls, usage=usage, stop_reason=stop, raw=resp)

    def add_tool_results(self, results: list[tuple[ToolCall, bool, str]]) -> None:
        for call, _ok, text in results:
            m = {"role": "tool", "tool_call_id": call.id, "content": text}
            self.messages.append(m)
            self.transcript.append(m)
