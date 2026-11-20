"""LLM judge panel for rubric items.

Each rubric item is a yes/no question answered by every judge on the panel. The panel takes a
majority vote; ties count as "no". A judge from the same model family as the subject never
grades that subject's work.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..tasks import TaskBundle

JUDGE_SYSTEM = (
    "You grade work produced by an AI assistant for a workplace task. You see the task, the "
    "deliverables and one criterion. Decide strictly whether the deliverables meet the criterion. "
    'Reply with JSON only: {"verdict": "yes" | "no", "reason": "<one sentence>"}.'
)


def deliverables_text(bundle: TaskBundle, snapshot: dict[str, Any], limit: int = 12000) -> str:
    """Everything the agent produced: answer, new or changed files, sent emails, chat posts."""
    state, parts = snapshot["state"], []
    parts.append(f"## Submitted answer\n{snapshot.get('answer') or '(none)'}")
    for path, f in state["drive"]["files"].items():
        before = bundle.workspace.get(path) or (bundle.world.get("drive", {}).get("files", {}) or {}).get(
            path
        )
        if f["content"] != before:
            parts.append(f"## File {path}\n{f['content']}")
    for m in state["mail"]["messages"]:
        if m["folder"] == "sent" and not m.get("seeded"):
            parts.append(f"## Email to {', '.join(m['to'])}\nSubject: {m['subject']}\n\n{m['body']}")
    for ch, msgs in state["chat"]["channels"].items():
        for m in msgs:
            if not m.get("seeded"):
                parts.append(f"## Chat post in #{ch}\n{m['text']}")
    text = "\n\n".join(parts)
    return text[:limit]


def parse_verdict(text: str) -> bool | None:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if m:
        try:
            v = str(json.loads(m.group(0)).get("verdict", "")).lower()
            if v in ("yes", "no"):
                return v == "yes"
        except json.JSONDecodeError:
            pass
    low = (text or "").strip().lower()
    if low.startswith("yes"):
        return True
    if low.startswith("no"):
        return False
    return None


class JudgePanel:
    def __init__(self, judges: list[Any]):
        """judges: objects with .id, .family and .complete(system, user) -> str."""
        self.judges = judges

    def grade(
        self, bundle: TaskBundle, snapshot: dict[str, Any], subject_family: str | None = None
    ) -> list[dict[str, Any]]:
        panel = [j for j in self.judges if not subject_family or j.family != subject_family]
        work = deliverables_text(bundle, snapshot)
        rows = []
        for item in bundle.task.rubric:
            user = f"# Task\n{bundle.task.brief}\n\n# Deliverables\n{work}\n\n# Criterion\n{item.text}"
            votes = []
            for j in panel:
                try:
                    votes.append({"judge": j.id, "verdict": parse_verdict(j.complete(JUDGE_SYSTEM, user))})
                except Exception as e:
                    votes.append({"judge": j.id, "verdict": None, "error": str(e)[:200]})
            valid = [v["verdict"] for v in votes if v["verdict"] is not None]
            passed = (sum(valid) > len(valid) / 2) if valid else None
            rows.append(
                {
                    "id": item.id,
                    "type": "rubric",
                    "passed": passed,
                    "weight": item.weight,
                    "critical": item.critical,
                    "votes": votes,
                }
            )
        return rows
