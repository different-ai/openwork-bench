"""owb: the OpenWork Bench command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__


def _bundles(args: argparse.Namespace):
    from .tasks import load_all

    return load_all(Path(args.tasks_dir) if getattr(args, "tasks_dir", None) else None)


def cmd_tasks(args: argparse.Namespace) -> int:
    for b in _bundles(args):
        t = b.task
        print(f"{t.id:34} v{t.version}  {t.category:13} {t.difficulty:6} {t.split:11} {t.title}")
    return 0


def cmd_subjects(args: argparse.Namespace) -> int:
    from .subjects import load_subjects

    for s in load_subjects().values():
        extra = s.get("model") or ""
        print(f"{s['id']:28} {s['type']:10} {s.get('kind', ''):10} {extra:24} {s['label']}")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    from .models import load_catalog, load_lock, verify_catalog
    from .subjects import repo_root

    root = repo_root()
    lock = verify_catalog(root) if args.models_cmd == "verify" else load_lock(root)
    cat = {m["key"]: m for m in load_catalog(root).get("models", [])}
    bad = 0
    for key, m in cat.items():
        v = lock.get(key, {})
        ok = v.get("verified")
        bad += 0 if ok else 1
        mark = "ok " if ok else ("?? " if not v else "NO ")
        rev = (v.get("revision") or "")[:10]
        print(
            f"[{mark}] {key:24} {m['hf_repo']:52} license={v.get('license') or '-':12} rev={rev:10} {v.get('reason', 'not verified yet: run owb models verify')}"
        )
    return 1 if (bad and args.models_cmd == "verify") else 0


def cmd_openwork_check(args: argparse.Namespace) -> int:
    """Prove the OpenWork path end to end without calling a model."""
    from .harness.openwork_desktop import DENY_LOCAL_TOOLS, OpenWorkClient
    from .mcp_server import SERVER_NAME, HttpWorldServer
    from .providers.base import read_secret
    from .tasks import select

    if args.openwork_cdp:
        from .harness.openwork_connect import server_info

        info = server_info(args.openwork_cdp)
        client = OpenWorkClient(info["baseUrl"], token=info["token"])
        print(f"server: found at {info['baseUrl']} (owner token in memory)")
    else:
        client = OpenWorkClient(
            args.openwork_url,
            token=read_secret("OPENWORK_TOKEN"),
            host_token=read_secret("OPENWORK_HOST_TOKEN"),
        )
    bundle = select(_bundles(args), args.task)[0]
    with HttpWorldServer(bundle) as srv:
        ws = client.create_workspace(f"{args.workspace_root}/owb-check", "OpenWork Bench check")["id"]
        print(f"workspace: created {ws}")
        client.patch_config(
            ws,
            {
                "mcp": {SERVER_NAME: {"type": "remote", "url": srv.url, "enabled": True, "oauth": False}},
                "permission": dict(DENY_LOCAL_TOOLS),
            },
        )
        print("config: MCP world attached, local tools denied")
        client.reload_engine(ws)
        print("engine: reloaded")
        sid = client.create_session(ws, "OpenWork Bench check")
        print(f"session: created {sid}")
        status = client.status(ws)
        print(f"status: ok ({len(status)} busy sessions)")
    print("OpenWork path OK (no model was called)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .validate import validate_all

    report = validate_all(_bundles(args))
    bad = {k: v for k, v in report.items() if v}
    for tid, probs in report.items():
        mark = "ok " if not probs else "ERR"
        print(f"[{mark}] {tid}")
        for p in probs:
            print(f"       - {p}")
    print(f"\n{len(report) - len(bad)}/{len(report)} tasks valid")
    return 1 if bad else 0


def _judge_panel(ids: list[str], subjects: dict[str, Any]):
    if not ids:
        return None
    from .grading.judge import JudgePanel
    from .providers import complete

    class Judge:
        def __init__(self, cfg: dict[str, Any]):
            self.cfg, self.id, self.family = cfg, cfg["id"], cfg.get("family")

        def complete(self, system: str, user: str) -> str:
            return complete(self.cfg, system, user)

    return JudgePanel([Judge(subjects[i]) for i in ids])


def cmd_run(args: argparse.Namespace) -> int:
    from .grading import ScoringConfig
    from .index import load_index_config
    from .runner import run_subject
    from .subjects import load_subjects
    from .tasks import select

    subjects = load_subjects()
    cfg = load_index_config(args.index)
    bundles = select(_bundles(args), args.tasks)
    if not args.include_private:
        bundles = [
            b
            for b in bundles
            if b.task.split in cfg.get("tasks", {}).get("splits", ["public-dev", "public-test"])
        ]
    if not bundles:
        print("No tasks selected.", file=sys.stderr)
        return 2
    panel = _judge_panel([j for j in (args.judges or "").split(",") if j], subjects)
    ow = {
        k: v
        for k, v in {
            "url": getattr(args, "openwork_url", None),
            "cdp_url": getattr(args, "openwork_cdp", None),
            "workspace_root": getattr(args, "workspace_root", None),
            "workspace_id": getattr(args, "workspace_id", None),
            "mcp_host": getattr(args, "mcp_host", None),
            "mcp_advertise_host": getattr(args, "mcp_advertise_host", None),
        }.items()
        if v
    }
    repeats = args.repeats or int(cfg.get("repeats", 3))
    for sid in args.subjects:
        if sid not in subjects:
            print(f"Unknown subject {sid!r}. See `owb subjects`.", file=sys.stderr)
            return 2
        s = subjects[sid]
        if s.get("kind") == "openwork-desktop":
            s = {**s, "openwork": {**s.get("openwork", {}), **ow}}
        workers = (
            args.workers if s.get("kind") != "openwork-desktop" or getattr(args, "workers_set", True) else 1
        )
        print(f"\n▶ {s['label']}  ({len(bundles)} tasks × {repeats} repeats)")

        def progress(row: dict[str, Any]) -> None:
            flag = "✓" if row["success"] else ("!" if row["safety_violation"] else "·")
            print(f"  {flag} {row['task_id']:32} r{row['repeat']}  score {row['score']:.2f}  {row['status']}")

        run_dir = run_subject(
            s,
            bundles,
            Path(args.out),
            repeats=repeats,
            workers=workers,
            index_version=cfg["version"],
            scoring=ScoringConfig.from_dict(cfg.get("scoring")),
            judge_panel=panel,
            progress=None if args.quiet else progress,
        )
        m = json.loads((run_dir / "manifest.json").read_text())
        print(f"  → {run_dir}  mean score {m['summary']['mean_score']:.3f}  errors {m['summary']['errors']}")
    return 0


def cmd_regrade(args: argparse.Namespace) -> int:
    from .grading import ScoringConfig
    from .index import load_index_config
    from .runner import regrade

    cfg = load_index_config(args.index)
    bundles = {b.id: b for b in _bundles(args)}
    for d in args.run_dirs:
        n = regrade(Path(d), bundles, ScoringConfig.from_dict(cfg.get("scoring")))
        print(f"{d}: {n} rows changed")
    return 0


def build_lb(
    run_paths: list[str], index_ref: str | None, any_index: bool, tasks_dir: str | None = None
) -> dict[str, Any]:
    from .index import build_leaderboard, load_errata, load_index_config
    from .runner import load_rows
    from .tasks import load_all

    cfg = load_index_config(index_ref)
    rows = load_rows([Path(p) for p in run_paths])
    bundles = load_all(Path(tasks_dir) if tasks_dir else None)
    return build_leaderboard(
        rows, bundles, cfg, load_errata(), any_index_version=any_index, sources={"paths": run_paths}
    )


def cmd_leaderboard(args: argparse.Namespace) -> int:
    from .index import summary_table

    lb = build_lb(args.runs, args.index, args.any_index, getattr(args, "tasks_dir", None))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(lb, indent=1))
    print(summary_table(lb))
    print(f"\nWrote {out}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run the offline subjects end to end and write the leaderboard the site is built from."""
    from .index import summary_table
    from .subjects import load_subjects

    subjects = load_subjects()
    offline = [s for s, c in subjects.items() if c.get("kind") in ("scripted", "noop", "simulated")]
    ns = argparse.Namespace(
        subjects=offline,
        tasks="all",
        repeats=args.repeats,
        workers=args.workers,
        out=args.out,
        index=args.index,
        judges="",
        include_private=False,
        quiet=True,
        tasks_dir=getattr(args, "tasks_dir", None),
    )
    cmd_run(ns)
    lb = build_lb([args.out], args.index, False, getattr(args, "tasks_dir", None))
    out = Path(args.out) / "leaderboard.json"
    out.write_text(json.dumps(lb, indent=1))
    print("\n" + summary_table(lb))
    site_data = Path(args.site_data)
    site_data.parent.mkdir(parents=True, exist_ok=True)
    site_data.write_text(out.read_text())
    print(f"\nLeaderboard: {out}\nSite data: {site_data} (cd site && npm run dev)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    run = Path(args.run_dir)
    rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines() if line.strip()]
    if args.task:
        traj = json.loads((run / "trajectories" / f"{args.task}__r{args.repeat}.json").read_text())
        row = next(r for r in rows if r["task_id"] == args.task and r["repeat"] == args.repeat)
        print(f"{args.task} r{args.repeat}: score {row['score']} status {row['status']}\n")
        for a in traj["actions"]:
            mark = "ok " if a.get("ok") else "ERR"
            print(f"  {a['step']:>3} [{mark}] {a['tool']}({json.dumps(a['args'])[:140]})")
        print(f"\nanswer: {traj['answer']!r}\n")
        for c in row["checks"]:
            print(f"  [{'pass' if c['passed'] else 'FAIL'}] {c['id']} {c['detail']}")
        for s in row["safety"]:
            if s["violated"]:
                print(f"  [UNSAFE] {s['id']} {s['detail']}")
        return 0
    for r in rows:
        print(
            f"{r['task_id']:34} r{r['repeat']}  {r['score']:.2f}  {'success' if r['success'] else ''}  {r['status']}"
        )
    return 0


def cmd_world_serve(args: argparse.Namespace) -> int:
    from .tasks import select

    b = select(_bundles(args), args.task)
    if len(b) != 1:
        print(f"Task {args.task!r} matched {len(b)} tasks", file=sys.stderr)
        return 2
    state = Path(args.state_out) if args.state_out else None
    if args.http:
        from .mcp_server import serve_http

        serve_http(b[0], args.host, args.port, state)
    else:
        from .mcp_server import serve

        serve(b[0], state)
    return 0


def cmd_world_plan(args: argparse.Namespace) -> int:
    from .world_plan import load_world_spec, plan, render

    p = plan(
        load_world_spec(Path(args.world)), Path(args.tasks_dir) if getattr(args, "tasks_dir", None) else None
    )
    print(json.dumps(p, indent=1) if args.json else render(p))
    return 1 if p["problems"] else 0


def cmd_grade_state(args: argparse.Namespace) -> int:
    from .grading import grade
    from .tasks import select

    b = select(_bundles(args), args.task)[0]
    snap = json.loads(Path(args.state).read_text())
    g = grade(b, snap)
    print(json.dumps({k: g[k] for k in ("score", "success", "safety_violation")}, indent=1))
    for c in g["checks"]:
        print(f"  [{'pass' if c['passed'] else 'FAIL'}] {c['id']} {c['detail']}")
    return 0


def cmd_hub(args: argparse.Namespace) -> int:
    from . import hub

    if args.hub_cmd == "export-tasks":
        out = hub.export_tasks(
            _bundles(args), Path(args.out), revision=args.revision, include_private=args.include_private
        )
        print(f"Exported to {out}")
    elif args.hub_cmd == "push-tasks":
        folder = hub.export_tasks(_bundles(args), Path(args.out), revision=args.tag or "main")
        print(hub.push_tasks(folder, repo_id=args.repo, tag=args.tag, create_pr=args.pr))
    elif args.hub_cmd == "push-run":
        for d in args.run_dirs:
            print(
                hub.push_run(
                    Path(d),
                    repo_id=args.repo,
                    create_pr=not args.direct,
                    include_trajectories=not args.no_trajectories,
                )
            )
    elif args.hub_cmd == "pull-results":
        print(
            hub.pull_results(
                Path(args.dest), repo_id=args.repo, revision=args.revision, trajectories=args.trajectories
            )
        )
    elif args.hub_cmd == "publish-leaderboard":
        print(hub.publish_leaderboard(Path(args.leaderboard), repo_id=args.repo, tag=args.tag))
    return 0


def build_parser() -> argparse.ArgumentParser:
    from .hub import RESULTS_REPO, TASKS_REPO

    p = argparse.ArgumentParser(
        prog="owb", description="OpenWork Bench: benchmark AI agents on knowledge work."
    )
    p.add_argument("--version", action="version", version=f"owb {__version__}")
    p.add_argument("--tasks-dir", help="Task folder (default: ./tasks)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tasks", help="List tasks").set_defaults(fn=cmd_tasks)
    sub.add_parser("subjects", help="List subjects").set_defaults(fn=cmd_subjects)
    sub.add_parser("validate", help="Check every task is solvable and not gameable").set_defaults(
        fn=cmd_validate
    )

    oc = sub.add_parser("openwork", help="OpenWork Desktop helpers")
    ocsub = oc.add_subparsers(dest="openwork_cmd", required=True)
    chk = ocsub.add_parser(
        "check", help="Prove the OpenWork path (workspace, config, MCP, session) without calling a model"
    )
    chk.add_argument("--openwork-cdp", help="DevTools URL of the running desktop, e.g. http://127.0.0.1:9825")
    chk.add_argument("--openwork-url", default="http://127.0.0.1:8787")
    chk.add_argument("--workspace-root", default="/tmp/owb-workspaces")
    chk.add_argument("--task", default="expense-policy-answer")
    chk.set_defaults(fn=cmd_openwork_check)

    mo = sub.add_parser("models", help="The open-weight model catalog")
    mosub = mo.add_subparsers(dest="models_cmd", required=True)
    mosub.add_parser("list", help="Show models and their verification status")
    mosub.add_parser("verify", help="Check each model publishes open weights; pin revision and license")
    mo.set_defaults(fn=cmd_models)

    r = sub.add_parser("run", help="Run subjects on tasks")
    r.add_argument("subjects", nargs="+")
    r.add_argument("--tasks", default="all", help="all, a category, ids (comma separated) or an id prefix")
    r.add_argument("--repeats", type=int, default=None)
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--out", default="runs")
    r.add_argument("--index", default=None, help="Index version, e.g. v0.1 (default: latest)")
    r.add_argument("--judges", default="", help="Comma-separated subject ids to use as rubric judges")
    r.add_argument("--include-private", action="store_true")
    r.add_argument("--quiet", action="store_true")
    r.add_argument(
        "--openwork-url", help="OpenWork server URL for openwork-desktop subjects (or OPENWORK_URL)"
    )
    r.add_argument(
        "--openwork-cdp",
        help="Find the desktop's embedded server through its DevTools port, e.g. http://127.0.0.1:9825",
    )
    r.add_argument("--workspace-root", help="Where openwork-desktop creates one fresh workspace per attempt")
    r.add_argument(
        "--workspace-id", help="Reuse one existing OpenWork workspace instead of creating one per attempt"
    )
    r.add_argument("--mcp-host", help="Interface the task MCP world listens on (default 127.0.0.1)")
    r.add_argument("--mcp-advertise-host", help="Host the OpenWork engine uses to reach the MCP world")
    r.set_defaults(fn=cmd_run)

    g = sub.add_parser("regrade", help="Re-score stored runs with the current graders")
    g.add_argument("run_dirs", nargs="+")
    g.add_argument("--index", default=None)
    g.set_defaults(fn=cmd_regrade)

    lb = sub.add_parser("leaderboard", help="Build leaderboard.json from runs")
    lb.add_argument("--runs", nargs="+", default=["runs"])
    lb.add_argument("--index", default=None)
    lb.add_argument("--out", default="site/public/leaderboard.json")
    lb.add_argument("--any-index", action="store_true", help="Include rows from other index versions")
    lb.set_defaults(fn=cmd_leaderboard)

    d = sub.add_parser(
        "demo", help="Offline end-to-end demo: reference + simulated subjects and the leaderboard"
    )
    d.add_argument("--repeats", type=int, default=3)
    d.add_argument("--workers", type=int, default=8)
    d.add_argument("--out", default="runs-demo")
    d.add_argument(
        "--site-data", default="site/public/leaderboard.json", help="Where the site reads the leaderboard"
    )
    d.add_argument("--index", default=None)
    d.set_defaults(fn=cmd_demo)

    sh = sub.add_parser("show", help="Show a run, or one task's trajectory")
    sh.add_argument("run_dir")
    sh.add_argument("--task")
    sh.add_argument("--repeat", type=int, default=1)
    sh.set_defaults(fn=cmd_show)

    w = sub.add_parser("world", help="Work with a task's simulated workplace")
    wsub = w.add_subparsers(dest="world_cmd", required=True)
    ws = wsub.add_parser("serve", help="Serve a task's world as an MCP server over stdio")
    ws.add_argument("task")
    ws.add_argument("--state-out", help="Write the world snapshot here after every tool call")
    ws.add_argument("--http", action="store_true", help="Serve over streamable HTTP instead of stdio")
    ws.add_argument("--host", default="127.0.0.1")
    ws.add_argument("--port", type=int, default=8765)
    ws.set_defaults(fn=cmd_world_serve)
    wp = wsub.add_parser("plan", help="Check and price an OpenWork world run before starting it")
    wp.add_argument("--world", default="worlds/openwork-bench.world.yaml")
    wp.add_argument("--json", action="store_true")
    wp.set_defaults(fn=cmd_world_plan)

    gs = sub.add_parser("grade-state", help="Grade a saved world snapshot (e.g. from `owb world serve`)")
    gs.add_argument("task")
    gs.add_argument("state")
    gs.set_defaults(fn=cmd_grade_state)

    h = sub.add_parser("hub", help="Hugging Face Hub storage")
    hsub = h.add_subparsers(dest="hub_cmd", required=True)
    e = hsub.add_parser("export-tasks", help="Write the tasks dataset folder locally")
    e.add_argument("--out", default="dist/hf-tasks")
    e.add_argument("--revision", default="main")
    e.add_argument("--include-private", action="store_true")
    pt = hsub.add_parser("push-tasks", help="Export and push tasks; tag a release")
    pt.add_argument("--repo", default=TASKS_REPO)
    pt.add_argument("--tag", help="e.g. tasks-v0.1.0")
    pt.add_argument("--out", default="dist/hf-tasks")
    pt.add_argument("--pr", action="store_true", help="Open a Hub pull request instead of committing")
    pr = hsub.add_parser("push-run", help="Upload run folders (as a Hub pull request by default)")
    pr.add_argument("run_dirs", nargs="+")
    pr.add_argument("--repo", default=RESULTS_REPO)
    pr.add_argument("--direct", action="store_true", help="Commit directly instead of opening a pull request")
    pr.add_argument("--no-trajectories", action="store_true")
    pl = hsub.add_parser("pull-results", help="Download published results at a revision")
    pl.add_argument("--dest", default="hub-results")
    pl.add_argument("--repo", default=RESULTS_REPO)
    pl.add_argument("--revision", default=None)
    pl.add_argument("--trajectories", action="store_true")
    pb = hsub.add_parser("publish-leaderboard", help="Upload a leaderboard snapshot")
    pb.add_argument("leaderboard")
    pb.add_argument("--repo", default=RESULTS_REPO)
    pb.add_argument("--tag")
    h.set_defaults(fn=cmd_hub)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    args.workers_set = any(a == "--workers" or a.startswith("--workers=") for a in argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
