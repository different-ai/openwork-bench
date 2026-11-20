"""Model provider adapters. Each exposes a Conversation for the agent loop and complete() for judges."""

from __future__ import annotations

from typing import Any

from .base import Conversation, ModelReply, ToolCall, Usage


def make_conversation(
    cfg: dict[str, Any], system: str, tools: list[dict[str, Any]], client: Any = None
) -> Conversation:
    provider = cfg.get("provider")
    if provider == "anthropic":
        from .anthropic_provider import AnthropicConversation

        return AnthropicConversation(cfg, system, tools, client=client)
    if provider in ("openai", "openai-compatible", "openrouter"):
        from .openai_provider import OpenAIConversation

        return OpenAIConversation(cfg, system, tools, client=client)
    raise ValueError(f"Unknown provider {provider!r}; use 'anthropic' or 'openai'")


def complete(cfg: dict[str, Any], system: str, user: str, client: Any = None) -> str:
    """One-shot completion (used by judges)."""
    conv = make_conversation(cfg, system, [], client=client)
    conv.add_user(user)
    return conv.call().text


__all__ = ["Conversation", "ModelReply", "ToolCall", "Usage", "make_conversation", "complete"]
