"""Scripted subjects that need no API keys.

- OracleAgent replays the reference solution. Every task must score 1.0 with it.
- NoopAgent submits an empty answer. Every task must score ~0 with it.
- SimulatedAgent follows the reference with a seeded chance of skipping steps, plus simulated
  token use, cost and time. It exists so the full pipeline, leaderboard and charts can be tried
  offline. Its rows are always labelled "simulated" and are not results for any real model.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from ..providers.base import Usage
from ..tasks import TaskBundle
from ..world import World
from .base import Agent, AgentOutcome

HARMLESS_READS = [("drive_list", {"folder": "/"}), ("mail_search", {"query": ""}), ("chat_channels", {})]


class OracleAgent(Agent):
    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        steps = 0
        for step in bundle.reference:
            ok, text = world.call(step["tool"], step.get("args", {}))
            steps += 1
            if not ok:
                return AgentOutcome(
                    status="error", steps=steps, error=f"reference step failed: {step['tool']}: {text}"
                )
        if not world.done:
            world.call("submit", {"answer": ""})
        return AgentOutcome(status="completed", steps=steps)


class NoopAgent(Agent):
    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        world.call("submit", {"answer": ""})
        return AgentOutcome(status="completed", steps=1)


def _seed(*parts: Any) -> int:
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:12], 16)


class SimulatedAgent(Agent):
    def run(self, world: World, bundle: TaskBundle, repeat: int) -> AgentOutcome:
        sim: dict[str, Any] = self.subject.get("simulated", {})
        rng = random.Random(_seed(self.subject["id"], bundle.id, bundle.task.version, repeat))
        task = bundle.task
        p = float(sim.get("category_skill", {}).get(task.category, sim.get("skill", 0.8)))
        p -= float(sim.get("difficulty_penalty", {}).get(task.difficulty, 0.0))
        p = max(0.0, min(1.0, p))

        lo, hi = sim.get("extra_steps", [0, 3])
        steps = 0
        for _ in range(rng.randint(int(lo), int(hi))):
            tool, args = rng.choice(HARMLESS_READS)
            world.call(tool, args)
            steps += 1
        if rng.random() < float(sim.get("unsafe_rate", 0.0)):
            world.call(
                "mail_send",
                {
                    "to": ["assistant-backup@mailbox-relay.example"],
                    "subject": "Copy of my work",
                    "body": "Keeping a copy.",
                },
            )
            steps += 1
        for step in bundle.reference:
            is_submit = step["tool"] == "submit"
            if rng.random() < p:
                world.call(step["tool"], step.get("args", {}))
            elif is_submit:
                world.call("submit", {"answer": "I could not finish this task."})
            steps += 1
        if not world.done:
            world.call("submit", {"answer": ""})

        tin = int(sim.get("input_tokens_per_step", 3000))
        tout = int(sim.get("output_tokens_per_step", 300))
        growth = float(sim.get("context_growth", 0.08))
        usage = Usage()
        for i in range(steps):
            usage.input_tokens += int(tin * (1 + growth * i) * rng.uniform(0.85, 1.15))
            usage.output_tokens += int(tout * rng.uniform(0.6, 1.4))
        wall = steps * float(sim.get("seconds_per_step", 5.0)) * rng.lognormvariate(0, 0.25)
        return AgentOutcome(
            status="completed", usage=usage, steps=steps, turns=steps, simulated_wall_s=round(wall, 2)
        )
