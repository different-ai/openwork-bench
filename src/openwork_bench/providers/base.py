from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def read_secret(env_name: str) -> str | None:
    """A secret from the environment, or from the file named by <ENV>_FILE (mode-600, never logged)."""
    value = os.environ.get(env_name)
    if value:
        return value
    path = os.environ.get(f"{env_name}_FILE")
    if path and Path(path).is_file():
        return Path(path).read_text().strip() or None
    return None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ModelReply:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    stop_reason: str
    raw: Any = None
    billed_usd: float | None = None  # cost the provider reported for this call, when it reports one
    served_by: str | None = None  # upstream provider that served the call (routers like OpenRouter)


@dataclass
class Conversation:
    """Provider-native conversation state for one agent run."""

    cfg: dict[str, Any]
    system: str
    tools: list[dict[str, Any]]
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def add_user(self, text: str) -> None:
        raise NotImplementedError

    def call(self) -> ModelReply:
        raise NotImplementedError

    def add_tool_results(self, results: list[tuple[ToolCall, bool, str]]) -> None:
        raise NotImplementedError


def cost_usd(usage: Usage, pricing: dict[str, Any] | None) -> float | None:
    """USD cost from token usage and per-million-token prices. None when prices are unknown."""
    if not pricing or pricing.get("input_per_mtok") is None:
        return None
    inp = float(pricing["input_per_mtok"])
    out = float(pricing.get("output_per_mtok", 0))
    cr = float(pricing.get("cache_read_per_mtok", inp * 0.1))
    cw = float(pricing.get("cache_write_per_mtok", inp * 1.25))
    total = (
        usage.input_tokens * inp
        + usage.output_tokens * out
        + usage.cache_read_tokens * cr
        + usage.cache_write_tokens * cw
    ) / 1_000_000
    return round(total, 6)
