"""Run subjects on tasks and store results.

Layout of one run (the unit uploaded to Hugging Face):

    runs/<run_id>/
      manifest.json             what was run: subject config, suite fingerprint, code revision
      results.jsonl             one row per (task, repeat)
      trajectories/<task>__r<k>.json   transcript, action log and final world state
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import GRADER_VERSION, __version__
from .grading import ScoringConfig, grade
from .harness import make_agent
from .providers.base import cost_usd
from .subjects import config_hash, public_config
from .tasks import TaskBundle, suite_fingerprint
from .world import World


def git_revision(path: Path | None = None) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path or Path.cwd(),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path or Path.cwd(),
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "")
    except Exception:
        return None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def run_one(
    subject: dict[str, Any],
    bundle: TaskBundle,
    repeat: int,
    run_id: str,
    index_version: str,
    scoring: ScoringConfig,
    judge_panel: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    world = World(bundle.world, bundle.workspace)
    agent = make_agent(subject)
    started_at = _now()
    t0 = time.monotonic()
    outcome = agent.run(world, bundle, repeat)
    wall = (
        outcome.simulated_wall_s if outcome.simulated_wall_s is not None else round(time.monotonic() - t0, 3)
    )
    snapshot = world.snapshot()
    graded = grade(
        bundle, snapshot, scoring=scoring, judge_panel=judge_panel, subject_family=subject.get("family")
    )
    row = {
        "run_id": run_id,
        "index_version": index_version,
        "subject_id": subject["id"],
        "subject_label": subject.get("label", subject["id"]),
        "subject_type": subject.get("type", "model"),
        "model": subject.get("model"),
        "harness": subject.get("harness", subject.get("kind")),
        "task_id": bundle.id,
        "task_version": bundle.task.version,
        "task_fingerprint": bundle.fingerprint(),
        "category": bundle.task.category,
        "split": bundle.task.split,
        "repeat": repeat,
        "status": outcome.status,
        "error": outcome.error,
        "score": graded["score"],
        "success": graded["success"],
        "critical_failed": graded["critical_failed"],
        "safety_violation": graded["safety_violation"],
        "checks": graded["checks"],
        "safety": graded["safety"],
        "rubric": graded["rubric"],
        "rubric_status": graded["rubric_status"],
        "usage": outcome.usage.as_dict(),
        "cost_usd": cost_usd(outcome.usage, subject.get("pricing")),
        "wall_s": wall,
        "steps": outcome.steps,
        "turns": outcome.turns,
        "simulated": subject.get("type") == "simulated",
        "grader_version": GRADER_VERSION,
        "started_at": started_at,
    }
    trajectory = {
        "run_id": run_id,
        "task_id": bundle.id,
        "task_version": bundle.task.version,
        "repeat": repeat,
        "status": outcome.status,
        "transcript": outcome.transcript,
        "actions": snapshot["actions"],
        "answer": snapshot["answer"],
        "final_state": snapshot["state"],
    }
    return row, trajectory


def make_run_id(subject_id: str) -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{subject_id}-{uuid.uuid4().hex[:6]}"


def run_subject(
    subject: dict[str, Any],
    bundles: list[TaskBundle],
    out_dir: Path,
    repeats: int = 3,
    workers: int = 4,
    index_version: str = "dev",
    scoring: ScoringConfig | None = None,
    judge_panel: Any = None,
    progress: Any = None,
) -> Path:
    scoring = scoring or ScoringConfig()
    run_id = make_run_id(subject["id"])
    run_dir = Path(out_dir) / run_id
    (run_dir / "trajectories").mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "created_at": _now(),
        "owb_version": __version__,
        "grader_version": GRADER_VERSION,
        "code_revision": git_revision(),
        "index_version": index_version,
        "subject": public_config(subject),
        "subject_config_hash": config_hash(subject),
        "suite_fingerprint": suite_fingerprint(bundles),
        "tasks": [{"id": b.id, "version": b.task.version, "fingerprint": b.fingerprint()} for b in bundles],
        "repeats": repeats,
        "scoring": scoring.__dict__,
        "python": platform.python_version(),
        "status": "running",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    jobs = [(b, r) for b in bundles for r in range(1, repeats + 1)]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(run_one, subject, b, r, run_id, index_version, scoring, judge_panel): (b, r)
            for b, r in jobs
        }
        for fut in as_completed(futures):
            b, r = futures[fut]
            row, traj = fut.result()
            rows.append(row)
            (run_dir / "trajectories" / f"{b.id}__r{r}.json").write_text(
                json.dumps(traj, indent=1, default=str)
            )
            if progress:
                progress(row)

    rows.sort(key=lambda x: (x["task_id"], x["repeat"]))
    with (run_dir / "results.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    manifest["status"] = "complete"
    manifest["completed_at"] = _now()
    manifest["summary"] = {
        "rows": len(rows),
        "mean_score": round(sum(r["score"] for r in rows) / max(1, len(rows)), 4),
        "errors": sum(1 for r in rows if r["status"] == "error"),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return run_dir


def regrade(run_dir: Path, bundles: dict[str, TaskBundle], scoring: ScoringConfig | None = None) -> int:
    """Re-score stored final states with the current graders. No agent is re-run.

    Used after a grader fix (see docs/versioning.md). Rows whose task version no longer matches
    the current task are left alone and marked stale.
    """
    scoring = scoring or ScoringConfig()
    run_dir = Path(run_dir)
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text().splitlines() if line.strip()]
    changed = 0
    for row in rows:
        b = bundles.get(row["task_id"])
        if b is None or b.task.version != row["task_version"]:
            row["stale"] = True
            continue
        traj = json.loads((run_dir / "trajectories" / f"{row['task_id']}__r{row['repeat']}.json").read_text())
        snapshot = {"state": traj["final_state"], "actions": traj["actions"], "answer": traj["answer"]}
        g = grade(b, snapshot, scoring=scoring)
        if g["score"] != row["score"] or g["grader_version"] != row.get("grader_version"):
            changed += 1
        rubric_keep = row.get("rubric") if row.get("rubric_status") == "graded" else g["rubric"]
        row.update(
            {
                k: g[k]
                for k in (
                    "score",
                    "success",
                    "critical_failed",
                    "safety_violation",
                    "checks",
                    "safety",
                    "grader_version",
                )
            }
        )
        row["rubric"] = rubric_keep
        row["regraded_at"] = _now()
    with (run_dir / "results.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    return changed


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    """Load result rows from run folders, results.jsonl files, or directories containing runs."""
    rows: list[dict[str, Any]] = []
    for p in paths:
        p = Path(p)
        files = [p] if p.is_file() else sorted(p.rglob("results.jsonl"))
        for f in files:
            rows.extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())
    return rows
