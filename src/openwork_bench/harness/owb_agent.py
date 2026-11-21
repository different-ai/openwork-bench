"""owb-agent: a plain tool-calling loop. The neutral harness for comparing models."""

from __future__ import annotations

import time
from typing import Any

from ..providers import make_conversation
from ..providers.base import Usage
from ..tasks import TaskBundle
from ..world import World
from .base import Agent, AgentOutcome, system_prompt

MAX_TOOL_RESULT_CHARS = 20_000


class OwbAgent(Agent):
    def __init__(self, subject: dict[str, Any], client: Any = None):
        super().__init__(subject)
        self.client = client  # injectable for tests

    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        budgets = bundle.task.budgets
        tools = [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in world.tool_specs()
        ]
        conv = make_conversation(self.subject, system_prompt(world), tools, client=self.client)
        conv.add_user(bundle.task.brief)
        usage, steps, turns = Usage(), 0, 0
        billed: float | None = None
        served_by: list[str] = []
        started = time.monotonic()
        status = "completed"
        try:
            while not world.done:
                if steps >= budgets.max_steps:
                    status = "budget_steps"
                    break
                if usage.budgeted >= budgets.max_tokens:
                    status = "budget_tokens"
                    break
                if time.monotonic() - started > budgets.timeout_s:
                    status = "timeout"
                    break
                reply = conv.call()
                usage.add(reply.usage)
                if reply.billed_usd is not None:
                    billed = (billed or 0.0) + reply.billed_usd
                if reply.served_by and reply.served_by not in served_by:
                    served_by.append(reply.served_by)
                turns += 1
                if reply.stop_reason == "refusal":
                    status = "refused"
                    break
                if not reply.tool_calls:
                    # The model stopped without calling submit: its last text is the answer.
                    world.answer = reply.text
                    status = "no_submit"
                    break
                results = []
                for call in reply.tool_calls:
                    if steps >= budgets.max_steps or world.done:
                        results.append(
                            (call, False, "Error: not run (step budget reached or task already submitted)")
                        )
                        continue
                    ok, text = world.call(call.name, call.args)
                    steps += 1
                    if len(text) > MAX_TOOL_RESULT_CHARS:
                        text = text[:MAX_TOOL_RESULT_CHARS] + "\n...[truncated]"
                    results.append((call, ok, text))
                conv.add_tool_results(results)
        except Exception as e:  # provider/network errors: recorded, excluded from scoring, re-runnable
            return AgentOutcome(
                status="error",
                usage=usage,
                steps=steps,
                turns=turns,
                transcript=conv.transcript,
                error=f"{type(e).__name__}: {e}"[:500],
                billed_usd=billed,
                served_by=served_by,
            )
        return AgentOutcome(
            status=status,
            usage=usage,
            steps=steps,
            turns=turns,
            transcript=conv.transcript,
            billed_usd=billed,
            served_by=served_by,
        )
