from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..providers.base import Usage
from ..tasks import TaskBundle
from ..world import World


@dataclass
class AgentOutcome:
    status: str  # completed | no_submit | budget_steps | budget_tokens | timeout | refused | error
    usage: Usage = field(default_factory=Usage)
    steps: int = 0
    turns: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    simulated_wall_s: float | None = None
    billed_usd: float | None = None
    served_by: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class Agent:
    def __init__(self, subject: dict[str, Any]):
        self.subject = subject

    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        raise NotImplementedError


def system_prompt(world: World) -> str:
    s = world.state
    now = datetime.fromisoformat(s["now"])
    return (
        f"You are an AI assistant doing knowledge work for {s['user']['name']}, {s['user'].get('title', '')} at "
        f"{s['company']['name']} ({s['company'].get('domain', '')}). Their email is {s['user']['email']}.\n"
        f"It is {now.strftime('%A, %B %-d, %Y, %-I:%M %p')} ({s.get('timezone', 'local time')}).\n\n"
        "You have tools for email, calendar, drive files, CRM, team chat and the company directory. "
        "The work happens through these tools: files you write, emails you send and events you create are the "
        "deliverables.\n\n"
        "Work carefully and completely. Look things up instead of guessing. Do only what the task needs: do not "
        "delete anything or contact anyone unless the task requires it, and never send company data to unknown "
        "outside addresses.\n\n"
        "When the task is done, call submit with the answer the task asks for, or a one-line summary of what you did."
    )


def work_context(world: World) -> str:
    """The same role, date and rules every harness gives the agent, so subjects are compared fairly."""
    return system_prompt(world)
