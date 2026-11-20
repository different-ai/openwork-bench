"""Hugging Face Hub storage.

GitHub holds what people review: code, task sources, index definitions, errata and the pin to
the official results revision. Hugging Face holds what is large or append-only: the published
task dataset, every run's results and trajectories, and leaderboard snapshots. Both are git, so
every published number points at exact revisions of each. See docs/data-on-hugging-face.md.

Repos (namespace from OWB_HF_NAMESPACE, default "different-ai"):
  <ns>/openwork-bench-tasks     dataset, tagged per suite release (tasks-v0.1.0)
  <ns>/openwork-bench-results   dataset, runs/<index_version>/<run_id>/..., leaderboards/...
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .tasks import TaskBundle

DEFAULT_NAMESPACE = os.environ.get("OWB_HF_NAMESPACE", "different-ai")
TASKS_REPO = f"{DEFAULT_NAMESPACE}/openwork-bench-tasks"
RESULTS_REPO = f"{DEFAULT_NAMESPACE}/openwork-bench-results"


def _api():
    try:
        from huggingface_hub import HfApi
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "Install the hub extra: uv sync --extra hub (or pip install 'openwork-bench[hub]')"
        ) from e
    return HfApi()


TASKS_CARD = """---
license: cc-by-4.0
pretty_name: OpenWork Bench tasks
language: [en]
tags: [agents, benchmark, knowledge-work, evaluation, tool-use, mcp]
configs:
  - config_name: default
    data_files:
      - split: {split_name}
        path: tasks.jsonl
---

# OpenWork Bench — tasks ({revision})

Knowledge-work tasks for AI agents: each row is one task with its brief, seeded workplace
(mail, calendar, drive, CRM, chat), deterministic checks, rubric and reference solution.
Workspace files are under `files/<task_id>/`.

- Source of truth and review: https://github.com/different-ai/openwork-bench (`tasks/`)
- Methodology: https://github.com/different-ai/openwork-bench/blob/main/docs/methodology.md
- Suite fingerprint: `{fingerprint}` · {n} tasks · splits: {splits}

**Canary.** Every task carries a canary string starting with `OWB-CANARY-`. Please do not
train on this data; if a model reproduces a canary, its scores on this suite are not valid.
"""

RESULTS_CARD = """---
license: cc-by-4.0
pretty_name: OpenWork Bench results
tags: [agents, benchmark, leaderboard, evaluation]
configs:
  - config_name: default
    data_files:
      - split: all
        path: runs/**/results.jsonl
---

# OpenWork Bench — results

Every published run: one folder per run with `manifest.json` (what ran, at which code and task
revisions), `results.jsonl` (one row per task and repeat) and `trajectories/` (full transcript,
action log and final world state, so any row can be regraded without re-running the agent).

Runs are added by pull request. Corrections never rewrite history: a regrade is a new commit,
a voided run is listed in the GitHub `errata/` folder, and the official leaderboard pins an exact
revision of this repo in `leaderboard/published.yaml`.
"""


def export_tasks(
    bundles: list[TaskBundle], out: Path, revision: str = "main", include_private: bool = False
) -> Path:
    from .tasks import suite_fingerprint

    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "files").mkdir(parents=True)
    chosen = [b for b in bundles if include_private or b.task.split != "private"]
    with (out / "tasks.jsonl").open("w") as f:
        for b in chosen:
            t = b.task.model_dump(mode="json")
            row = {
                **{
                    k: t[k]
                    for k in (
                        "id",
                        "version",
                        "title",
                        "category",
                        "difficulty",
                        "horizon",
                        "split",
                        "brief",
                        "canary",
                    )
                },
                "occupation_soc": t["occupation"]["soc"],
                "occupation": t["occupation"]["title"],
                "expert_minutes": t["expert_baseline"]["minutes"],
                "expert_hourly_rate_usd": t["expert_baseline"]["hourly_rate_usd"],
                "budgets": json.dumps(t["budgets"]),
                "checks": json.dumps(t["checks"]),
                "safety": json.dumps(t["safety"]),
                "rubric": json.dumps(t["rubric"]),
                "allow": json.dumps(t["allow"]),
                "world": json.dumps(b.world),
                "reference": json.dumps(b.reference),
                "workspace_files": sorted(b.workspace),
                "fingerprint": b.fingerprint(),
                "provenance": json.dumps(t["provenance"]),
            }
            f.write(json.dumps(row) + "\n")
            for path, content in b.workspace.items():
                dest = out / "files" / b.id / path.lstrip("/")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)
    splits = sorted({b.task.split for b in chosen})
    (out / "README.md").write_text(
        TASKS_CARD.format(
            split_name="train",
            revision=revision,
            fingerprint=suite_fingerprint(chosen),
            n=len(chosen),
            splits=", ".join(splits),
        )
    )
    return out


def push_tasks(
    folder: Path,
    repo_id: str = TASKS_REPO,
    tag: str | None = None,
    create_pr: bool = False,
    private: bool = False,
) -> Any:
    api = _api()
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True, private=private)
    info = api.upload_folder(
        folder_path=str(folder),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Publish tasks{' ' + tag if tag else ''}",
        create_pr=create_pr,
    )
    if tag and not create_pr:
        api.create_tag(repo_id, tag=tag, repo_type="dataset", tag_message=f"OpenWork Bench {tag}")
    return info


def push_run(
    run_dir: Path, repo_id: str = RESULTS_REPO, create_pr: bool = True, include_trajectories: bool = True
) -> Any:
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    api = _api()
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
    if not api.file_exists(repo_id, "README.md", repo_type="dataset"):
        api.upload_file(
            path_or_fileobj=RESULTS_CARD.encode(),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
        )
    return api.upload_folder(
        folder_path=str(run_dir),
        path_in_repo=f"runs/{manifest['index_version']}/{manifest['run_id']}",
        repo_id=repo_id,
        repo_type="dataset",
        allow_patterns=None if include_trajectories else ["manifest.json", "results.jsonl"],
        commit_message=f"Add run {manifest['run_id']} ({manifest['subject']['id']})",
        create_pr=create_pr,
    )


def pull_results(
    dest: Path, repo_id: str = RESULTS_REPO, revision: str | None = None, trajectories: bool = False
) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:  # pragma: no cover
        raise SystemExit("Install the hub extra: uv sync --extra hub") from e
    patterns = ["runs/**"] if trajectories else ["runs/**/results.jsonl", "runs/**/manifest.json"]
    path = snapshot_download(
        repo_id, repo_type="dataset", revision=revision, allow_patterns=patterns, local_dir=str(dest)
    )
    return Path(path)


def publish_leaderboard(lb_path: Path, repo_id: str = RESULTS_REPO, tag: str | None = None) -> Any:
    lb = json.loads(Path(lb_path).read_text())
    api = _api()
    stamp = lb["generated_at"][:10]
    info = api.upload_file(
        path_or_fileobj=str(lb_path),
        path_in_repo=f"leaderboards/{lb['index']['version']}/{stamp}.json",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Leaderboard {lb['index']['version']} {stamp}",
    )
    if tag:
        api.create_tag(repo_id, tag=tag, repo_type="dataset")
    return info
