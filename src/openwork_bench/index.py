"""The OpenWork Bench Index: turn result rows into a versioned leaderboard."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .schema import CATEGORIES
from .subjects import repo_root
from .tasks import TaskBundle


def load_index_config(ref: str | Path | None = None) -> dict[str, Any]:
    """Load index/<version>.yaml. ref may be a path, a version like 'v0.1', or None for the latest."""
    root = repo_root() / "index"
    if ref is None:
        files = sorted(root.glob("v*.yaml"))
        if not files:
            raise FileNotFoundError("no index/v*.yaml files")
        path = files[-1]
    else:
        path = Path(ref)
        if not path.exists():
            path = root / (str(ref) if str(ref).endswith(".yaml") else f"{ref}.yaml")
    cfg = yaml.safe_load(path.read_text())
    cfg["_path"] = str(path)
    return cfg


def load_errata(root: Path | None = None) -> list[dict[str, Any]]:
    out = []
    for f in sorted(((root or repo_root()) / "errata").glob("*.yaml")):
        e = yaml.safe_load(f.read_text()) or {}
        if e and not e.get("example"):
            out.append(e)
    return out


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _index_from(
    task_scores: dict[str, list[float]], task_cat: dict[str, str], weights: dict[str, float]
) -> float | None:
    by_cat: dict[str, list[float]] = defaultdict(list)
    for t, scores in task_scores.items():
        if scores:
            by_cat[task_cat[t]].append(sum(scores) / len(scores))
    num = den = 0.0
    for cat, w in weights.items():
        if by_cat.get(cat):
            num += w * (sum(by_cat[cat]) / len(by_cat[cat]))
            den += w
    return 100 * num / den if den else None


def bootstrap_ci(
    task_scores: dict[str, list[float]],
    task_cat: dict[str, str],
    weights: dict[str, float],
    iterations: int,
    seed: int,
) -> tuple[float, float] | None:
    """95% CI by resampling tasks within each category and repeats within each task."""
    rng = random.Random(seed)
    by_cat: dict[str, list[str]] = defaultdict(list)
    for t in task_scores:
        by_cat[task_cat[t]].append(t)
    samples = []
    for _ in range(iterations):
        resampled: dict[str, list[float]] = {}
        for _cat, tasks in by_cat.items():
            for i in range(len(tasks)):
                t = rng.choice(tasks)
                reps = task_scores[t]
                resampled[f"{t}#{i}"] = [rng.choice(reps) for _ in reps]
        cat_map = {k: task_cat[k.split("#")[0]] for k in resampled}
        v = _index_from(resampled, cat_map, weights)
        if v is not None:
            samples.append(v)
    if not samples:
        return None
    samples.sort()
    return round(samples[int(0.025 * len(samples))], 2), round(
        samples[min(len(samples) - 1, int(0.975 * len(samples)))], 2
    )


def build_leaderboard(
    rows: list[dict[str, Any]],
    bundles: list[TaskBundle],
    cfg: dict[str, Any],
    errata: list[dict[str, Any]] | None = None,
    any_index_version: bool = False,
    sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errata = errata or []
    splits = cfg.get("tasks", {}).get("splits", ["public-dev", "public-test"])
    tasks = {b.id: b for b in bundles if b.task.split in splits}
    task_cat = {t: b.task.category for t, b in tasks.items()}
    raw_weights = cfg.get("categories", {c: 1 for c in CATEGORIES})
    total_w = sum(float(w) for w in raw_weights.values()) or 1.0
    weights = {c: float(w) / total_w for c, w in raw_weights.items()}
    boot = cfg.get("bootstrap", {"iterations": 1000, "seed": 7})

    void_runs = {r for e in errata if e.get("action") == "void" for r in e.get("affects", {}).get("runs", [])}
    void_subjects = {
        s for e in errata if e.get("action") == "void" for s in e.get("affects", {}).get("subjects", [])
    }

    # Keep rows for this index version, current task versions, not voided, not infra errors.
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        sid = r["subject_id"]
        if not any_index_version and r.get("index_version") != cfg["version"]:
            continue
        if r["task_id"] not in tasks:
            continue
        if r["run_id"] in void_runs or sid in void_subjects:
            counts[sid]["voided"] += 1
            continue
        if r["task_version"] != tasks[r["task_id"]].task.version:
            counts[sid]["stale"] += 1
            continue
        if r["status"] == "error":
            counts[sid]["errors"] += 1
            continue
        by_subject[sid].append(r)

    subjects_out = []
    for sid, srows in by_subject.items():
        # Latest run wins per task (run ids start with a UTC timestamp).
        latest: dict[str, str] = {}
        for r in srows:
            if r["task_id"] not in latest or r["run_id"] > latest[r["task_id"]]:
                latest[r["task_id"]] = r["run_id"]
        srows = [r for r in srows if latest[r["task_id"]] == r["run_id"]]
        per_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in srows:
            per_task[r["task_id"]].append(r)
        task_scores = {t: [r["score"] for r in rs] for t, rs in per_task.items()}

        cats: dict[str, float | None] = {}
        for c in weights:
            vals = [sum(s) / len(s) for t, s in task_scores.items() if task_cat[t] == c]
            cats[c] = round(100 * sum(vals) / len(vals), 2) if vals else None
        index = _index_from(task_scores, task_cat, weights)
        ci = bootstrap_ci(
            task_scores, task_cat, weights, int(boot.get("iterations", 1000)), int(boot.get("seed", 7))
        )
        k = min(len(rs) for rs in per_task.values())
        pass_hat_k = _mean([1.0 if all(r["success"] for r in rs) else 0.0 for rs in per_task.values()])
        costs = [r.get("cost_usd") for r in srows]
        cost = _mean(costs) if all(c is not None for c in costs) else None
        wall = _mean([r.get("wall_s") for r in srows])
        expert_value = _mean(
            [tasks[t].task.expert_baseline.cost_usd * (sum(s) / len(s)) for t, s in task_scores.items()]
        )
        expert_secs = _mean([tasks[t].task.expert_baseline.minutes * 60 for t in task_scores])
        first = srows[0]
        subjects_out.append(
            {
                "id": sid,
                "label": first.get("subject_label", sid),
                "type": first.get("subject_type", "model"),
                "model": first.get("model"),
                "harness": first.get("harness"),
                "simulated": bool(first.get("simulated")),
                "index": round(index, 2) if index is not None else None,
                "ci": list(ci) if ci else None,
                "complete": set(per_task) == set(tasks),
                "coverage": round(len(per_task) / max(1, len(tasks)), 3),
                "categories": cats,
                "pass_at_1": round(_mean([1.0 if r["success"] else 0.0 for r in srows]) or 0, 4),
                "pass_hat_k": round(pass_hat_k or 0, 4),
                "k": k,
                "safety_rate": round(_mean([1.0 if r["safety_violation"] else 0.0 for r in srows]) or 0, 4),
                "cost_per_task": round(cost, 5) if cost is not None else None,
                "time_per_task": round(wall, 2) if wall is not None else None,
                "tokens_per_task": round(_mean([sum((r.get("usage") or {}).values()) for r in srows]) or 0),
                "steps_per_task": round(_mean([r.get("steps", 0) for r in srows]) or 0, 2),
                "value_per_dollar": round(expert_value / cost, 1) if cost else None,
                "speedup_vs_expert": round(expert_secs / wall, 1) if wall else None,
                "runs": sorted(set(latest.values())),
                "tasks": {
                    t: {
                        "score": round(sum(s) / len(s), 4),
                        "success_rate": round(
                            sum(1 for r in per_task[t] if r["success"]) / len(per_task[t]), 4
                        ),
                        "n": len(s),
                    }
                    for t, s in task_scores.items()
                },
                "excluded": dict(counts.get(sid, {})),
            }
        )
    subjects_out.sort(key=lambda s: (s["index"] is None, -(s["index"] or 0)))

    return {
        "index": {
            "name": cfg.get("name", "OpenWork Bench Index"),
            "version": cfg["version"],
            "status": cfg.get("status", "preview"),
            "repeats": cfg.get("repeats"),
            "scoring": cfg.get("scoring", {}),
            "categories": {
                c: {"label": CATEGORIES.get(c, c), "weight": round(w, 4)} for c, w in weights.items()
            },
            "splits": splits,
        },
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "owb_version": __version__,
        "sources": sources or {},
        "errata_applied": [e.get("id") for e in errata],
        "tasks": [
            {
                "id": b.id,
                "version": b.task.version,
                "title": b.task.title,
                "category": b.task.category,
                "difficulty": b.task.difficulty,
                "horizon": b.task.horizon,
                "occupation": b.task.occupation.title,
                "expert_minutes": b.task.expert_baseline.minutes,
                "expert_cost_usd": b.task.expert_baseline.cost_usd,
            }
            for b in sorted(tasks.values(), key=lambda b: (list(CATEGORIES).index(b.task.category), b.id))
        ],
        "subjects": subjects_out,
    }


def summary_table(lb: dict[str, Any]) -> str:
    lines = [f"{lb['index']['name']} {lb['index']['version']} ({lb['index']['status']})", ""]
    lines.append(
        f"{'#':>2}  {'subject':34} {'index':>6} {'95% CI':>13} {'pass^k':>7} {'safety':>7} {'$/task':>8} {'s/task':>7}"
    )
    for i, s in enumerate(lb["subjects"], 1):
        ci = f"{s['ci'][0]:.1f}-{s['ci'][1]:.1f}" if s["ci"] else "-"
        cost = f"{s['cost_per_task']:.4f}" if s["cost_per_task"] is not None else "n/a"
        t = f"{s['time_per_task']:.1f}" if s["time_per_task"] is not None else "-"
        tag = " (sim)" if s["simulated"] else ""
        idx = f"{s['index']:.1f}" if s["index"] is not None else "-"
        lines.append(
            f"{i:>2}  {(s['label'] + tag)[:34]:34} {idx:>6} {ci:>13} {s['pass_hat_k']:>7.2f} {s['safety_rate']:>7.2f} {cost:>8} {t:>7}"
        )
    return "\n".join(lines)


__all__ = ["load_index_config", "load_errata", "build_leaderboard", "summary_table"]
