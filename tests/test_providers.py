"""The owb-agent loop against fake provider clients (no network, no keys)."""

import json
from types import SimpleNamespace as NS

from openwork_bench.grading import grade
from openwork_bench.harness.owb_agent import OwbAgent
from openwork_bench.world import World


class Block(NS):
    def model_dump(self, exclude_none=False):
        return dict(vars(self))


class FakeAnthropic:
    """Replays the expense-policy reference solution as Claude tool_use blocks."""

    def __init__(self, steps):
        self.steps, self.calls = list(steps), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.steps:
            s = self.steps.pop(0)
            content = [
                Block(type="text", text="Working."),
                Block(type="tool_use", id=f"t{len(self.calls)}", name=s["tool"], input=s["args"]),
            ]
            stop = "tool_use"
        else:
            content, stop = [Block(type="text", text="Done.")], "end_turn"
        return NS(
            content=content,
            stop_reason=stop,
            usage=NS(
                input_tokens=1000, output_tokens=100, cache_read_input_tokens=0, cache_creation_input_tokens=0
            ),
        )


class FakeOpenAI:
    def __init__(self, steps):
        self.steps, self.calls = list(steps), []
        self.chat = NS(completions=self)

    def create(self, **kw):
        self.calls.append(kw)
        s = self.steps.pop(0)
        tc = NS(id=f"c{len(self.calls)}", function=NS(name=s["tool"], arguments=json.dumps(s["args"])))
        msg = NS(content=None, tool_calls=[tc], refusal=None)
        return NS(
            choices=[NS(message=msg, finish_reason="tool_calls")],
            usage=NS(prompt_tokens=900, completion_tokens=80, prompt_tokens_details=None),
        )


def test_anthropic_loop_solves_task_and_meters_usage(by_id):
    b = by_id["expense-policy-answer"]
    fake = FakeAnthropic(b.reference)
    subject = {"id": "fake-claude", "provider": "anthropic", "model": "claude-opus-5-5", "effort": "high"}
    w = World(b.world, b.workspace)
    out = OwbAgent(subject, client=fake).run(w, b, 1)
    assert out.status == "completed" and w.done
    assert grade(b, w.snapshot())["score"] == 1.0
    assert out.usage.input_tokens == 1000 * len(b.reference)
    first = fake.calls[0]
    assert first["model"] == "claude-opus-5-5" and first["output_config"] == {"effort": "high"}
    assert {t["name"] for t in first["tools"]} >= {"mail_send", "submit"}
    # tool results go back as one user message of tool_result blocks
    assert fake.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"


def test_openai_loop_solves_task(by_id):
    b = by_id["expense-policy-answer"]
    fake = FakeOpenAI(b.reference)
    subject = {"id": "fake-gpt", "provider": "openai", "model": "some-model"}
    w = World(b.world, b.workspace)
    out = OwbAgent(subject, client=fake).run(w, b, 1)
    assert out.status == "completed"
    assert grade(b, w.snapshot())["score"] == 1.0
    assert fake.calls[1]["messages"][-1]["role"] == "tool"


def test_step_budget_is_enforced(by_id):
    b = by_id["vendor-shortlist"]
    looping = [{"tool": "drive_list", "args": {"folder": "/"}}] * 200
    w = World(b.world, b.workspace)
    out = OwbAgent({"id": "x", "provider": "anthropic", "model": "m"}, client=FakeAnthropic(looping)).run(
        w, b, 1
    )
    assert out.status == "budget_steps" and out.steps == b.task.budgets.max_steps


def test_provider_errors_are_recorded_not_raised(by_id):
    class Boom:
        messages = NS(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("503 overloaded")))

    b = by_id["vendor-shortlist"]
    out = OwbAgent({"id": "x", "provider": "anthropic", "model": "m"}, client=Boom()).run(
        World(b.world, b.workspace), b, 1
    )
    assert out.status == "error" and "503" in out.error
