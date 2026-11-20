"""Task validation: schema, solvability and outcome validity.

Following the Agentic Benchmark Checklist, every task must be:
  - solvable: the reference solution scores 1.0
  - not gameable by doing nothing: an empty submission scores near 0
"""

from __future__ import annotations

from typing import Any

from .grading import grade
from .grading.checks import CHECKS
from .harness.scripted import NoopAgent, OracleAgent
from .tasks import TaskBundle
from .world import World

CANARY_PREFIX = "OWB-CANARY-"
NOOP_MAX_SCORE = 0.15


def validate_bundle(b: TaskBundle) -> list[str]:
    problems: list[str] = []
    t = b.task
    if not t.canary.startswith(CANARY_PREFIX):
        problems.append(f"canary must start with {CANARY_PREFIX}")
    for c in [*t.checks, *t.safety]:
        if c.type not in CHECKS:
            problems.append(f"unknown check type {c.type!r} in {c.id}")
    if not any(c.critical for c in t.checks):
        problems.append("at least one check should be critical")
    if not b.reference:
        problems.append("missing reference.yaml solution")
        return problems
    if problems:
        return problems

    w = World(b.world, b.workspace)
    out = OracleAgent({"id": "oracle"}).run(w, b, 1)
    if out.status != "completed":
        problems.append(f"reference solution failed: {out.error}")
    else:
        g = grade(b, w.snapshot())
        if g["score"] < 1.0 or not g["success"]:
            failed = [f"{c['id']}: {c['detail']}" for c in g["checks"] if not c["passed"]]
            unsafe = [f"{s['id']}: {s['detail']}" for s in g["safety"] if s["violated"]]
            problems.append(f"reference scores {g['score']} (failed: {failed + unsafe})")

    w = World(b.world, b.workspace)
    NoopAgent({"id": "noop"}).run(w, b, 1)
    g = grade(b, w.snapshot())
    if g["score"] > NOOP_MAX_SCORE:
        passed = [c["id"] for c in g["checks"] if c["passed"]]
        problems.append(f"empty submission scores {g['score']} > {NOOP_MAX_SCORE} (passes {passed})")
    return problems


def validate_all(bundles: list[TaskBundle]) -> dict[str, list[str]]:
    report: dict[str, list[str]] = {}
    seen: dict[str, Any] = {}
    for b in bundles:
        probs = validate_bundle(b)
        if b.id in seen:
            probs.append(f"duplicate task id (also at {seen[b.id]})")
        seen[b.id] = b.path
        report[b.id] = probs
    return report
