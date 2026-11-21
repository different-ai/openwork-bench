"""Harnesses: the agent loops that drive a subject through a task.

A subject is `model x harness`. Built-in harnesses:
  - openwork-desktop: OpenWork Desktop's server and engine, with the task world attached over MCP
  - owb-agent: a plain tool-calling loop, the neutral control for comparing models
  - scripted:  replays the task's reference solution (the "oracle"; proves tasks are solvable)
  - noop:      submits nothing (proves graders do not reward empty work)
  - simulated: a seeded stochastic agent for testing the pipeline without API keys
External agent products (OpenWork, Claude Code, Codex, ...) connect over MCP; see docs/harness-adapters.md.
"""

from __future__ import annotations

from typing import Any

from .base import Agent, AgentOutcome


def make_agent(subject: dict[str, Any]) -> Agent:
    kind = subject.get("kind")
    if kind == "agent":
        from .owb_agent import OwbAgent

        return OwbAgent(subject)
    if kind == "openwork-desktop":
        from .openwork_desktop import OpenWorkDesktopAgent

        return OpenWorkDesktopAgent(subject)
    if kind == "scripted":
        from .scripted import OracleAgent

        return OracleAgent(subject)
    if kind == "noop":
        from .scripted import NoopAgent

        return NoopAgent(subject)
    if kind == "simulated":
        from .scripted import SimulatedAgent

        return SimulatedAgent(subject)
    raise ValueError(f"Unknown subject kind {kind!r}")


__all__ = ["Agent", "AgentOutcome", "make_agent"]
