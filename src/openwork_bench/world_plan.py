"""Plan an OpenWork world run: check the spec, select subjects, and price the run before it starts."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml

from .subjects import load_subjects
from .tasks import load_all, select


def load_world_spec(path: Path) -> dict[str, Any]:
    spec = yaml.safe_load(Path(path).read_text()) or {}
    for key in ("openwork", "bench", "budget"):
        if key not in spec:
            raise ValueError(f"{path}: missing '{key}' section")
    return spec


def plan(spec: dict[str, Any], tasks_dir: Path | None = None) -> dict[str, Any]:
    bench, ow, est, budget = spec["bench"], spec["openwork"], spec.get("estimates", {}), spec["budget"]
    subjects = load_subjects()
    harnesses = set(bench.get("harnesses", ["openwork-desktop"]))
    tiers = set(bench.get("tiers", [])) or None
    chosen = [
        s
        for s in subjects.values()
        if s.get("board") == bench.get("board", "open-weights")
        and s.get("harness") in harnesses
        and (tiers is None or s.get("tier") in tiers)
    ]
    for anchor in bench.get("anchors", []):
        if anchor in subjects:
            chosen.append(subjects[anchor])
    bundles = select(load_all(tasks_dir), str(bench.get("tasks", "all")))
    repeats = int(bench.get("repeats", 3))
    runs_per_subject = len(bundles) * repeats

    steps = float(est.get("steps_per_task", 14))
    tin = float(est.get("input_tokens_per_step", 6000)) * steps
    tout = float(est.get("output_tokens_per_step", 450)) * steps
    rows, problems = [], []
    total_usd, desktop_runs = 0.0, 0
    for s in chosen:
        p = s.get("pricing") or {}
        per_run = None
        if p.get("input_per_mtok") is not None:
            per_run = (tin * float(p["input_per_mtok"]) + tout * float(p.get("output_per_mtok", 0))) / 1e6
            total_usd += per_run * runs_per_subject
        if s.get("kind") == "openwork-desktop":
            desktop_runs += runs_per_subject
        weights = s.get("open_weights") or {}
        if s.get("board") == "open-weights" and not weights.get("verified"):
            problems.append(f"{s['id']}: weights not verified (run `owb models verify`)")
        rows.append(
            {
                "subject": s["id"],
                "harness": s.get("harness") or s.get("kind"),
                "tier": s.get("tier") or ("anchor" if s.get("anchor") else None),
                "runs": runs_per_subject,
                "est_usd_per_run": round(per_run, 4) if per_run is not None else None,
                "est_usd": round(per_run * runs_per_subject, 2) if per_run is not None else None,
                "weights_revision": (weights.get("revision") or "")[:12] or None,
            }
        )

    parallel = max(1, int(bench.get("parallel_sessions", 1)))
    hours = desktop_runs * steps * float(est.get("seconds_per_step", 8)) / parallel / 3600
    sandbox_usd = hours * float(est.get("sandbox_usd_per_hour", 0.27))
    if total_usd > float(budget.get("max_model_usd", math.inf)):
        problems.append(f"estimated model spend ${total_usd:.2f} exceeds budget ${budget['max_model_usd']}")
    if hours > float(budget.get("max_sandbox_hours", math.inf)):
        problems.append(
            f"estimated sandbox time {hours:.1f} h exceeds budget {budget['max_sandbox_hours']} h"
        )
    missing = [x["name"] for x in spec.get("secrets", []) if not os.environ.get(x["name"])]

    server = ow.get("server", {})
    desktop_ids = [r["subject"] for r in rows if r["harness"] == "openwork-desktop"]
    control_ids = [r["subject"] for r in rows if r["harness"] != "openwork-desktop"]
    steps_out = [
        f"(in different-ai/openwork) pnpm world plan {ow['world']} --place {ow['place']}",
        f"(in different-ai/openwork) pnpm world up {ow['world']} --place {ow['place']} -- --ref {ow.get('ref', 'dev')} --lifetime {ow.get('lifetime_minutes', 120)}",
        f"(in the sandbox) uv tool install 'git+https://github.com/different-ai/openwork-bench@{bench.get('ref', 'main')}[all]'",
        "(in the sandbox) owb models verify && owb validate",
        f"(in the sandbox) owb run {' '.join(desktop_ids) or '<subjects>'} --repeats {repeats} --openwork-url {server.get('url')} "
        f"--workspace-root {ow.get('workspace_root', '/tmp/owb-workspaces')} --workers {parallel}",
    ]
    if control_ids:
        steps_out.append(f"(anywhere) owb run {' '.join(control_ids)} --repeats {repeats}")
    steps_out += [
        "owb leaderboard --runs runs && owb site",
        f"owb hub push-run runs/<run_id>   # opens a pull request on {spec.get('publish', {}).get('results_repo', 'the results dataset')}",
        f"(in different-ai/openwork) pnpm world down {ow['world']}",
    ]
    return {
        "name": spec.get("name"),
        "openwork": {k: ow.get(k) for k in ("world", "place", "ref", "lifetime_minutes")},
        "tasks": len(bundles),
        "repeats": repeats,
        "subjects": rows,
        "totals": {
            "runs": runs_per_subject * len(rows),
            "est_model_usd": round(total_usd, 2),
            "est_sandbox_hours": round(hours, 2),
            "est_sandbox_usd": round(sandbox_usd, 2),
        },
        "budget": budget,
        "missing_secrets": missing,
        "problems": problems,
        "steps": steps_out,
    }


def render(p: dict[str, Any]) -> str:
    out = [
        f"World run: {p['name']}  ·  OpenWork {p['openwork']['world']} on {p['openwork']['place']} @ {p['openwork']['ref']}",
        f"{p['tasks']} tasks × {p['repeats']} repeats  ·  {len(p['subjects'])} subjects  ·  {p['totals']['runs']} runs",
        "",
        f"{'subject':44} {'harness':17} {'tier':10} {'runs':>5} {'est $':>9}  weights",
    ]
    for r in p["subjects"]:
        usd = f"{r['est_usd']:.2f}" if r["est_usd"] is not None else "n/a"
        out.append(
            f"{r['subject'][:44]:44} {r['harness'] or '':17} {r['tier'] or '':10} {r['runs']:>5} {usd:>9}  {r['weights_revision'] or '-'}"
        )
    t, b = p["totals"], p["budget"]
    out += [
        "",
        f"Estimated model spend   ${t['est_model_usd']:.2f}   (budget ${b.get('max_model_usd')})",
        f"Estimated sandbox time  {t['est_sandbox_hours']:.1f} h ≈ ${t['est_sandbox_usd']:.2f}   (budget {b.get('max_sandbox_hours')} h)",
        "Estimates use planning assumptions from the world spec; real runs record billed cost.",
    ]
    if p["missing_secrets"]:
        out.append(f"Secrets not set in this shell: {', '.join(p['missing_secrets'])}")
    out += ["", "Problems:" if p["problems"] else "Problems: none"] + [f"  - {x}" for x in p["problems"]]
    out += ["", "Steps:"] + [f"  {i}. {s}" for i, s in enumerate(p["steps"], 1)]
    return "\n".join(out)
