#!/usr/bin/env bash
# Runs inside an OpenWork world sandbox. Usage:
#   world-run.sh setup <bench-sha>            clone openwork-bench at a commit and install it
#   world-run.sh check                        prove the OpenWork path without calling a model
#   world-run.sh stage <world-spec> <stage>   run one stage (needs OPENROUTER_API_KEY_FILE)
set -euo pipefail
BENCH_DIR="${BENCH_DIR:-/root/openwork-bench}"
CDP="${OPENWORK_CDP_URL:-http://127.0.0.1:9825}"
WS_ROOT="${OWB_WORKSPACE_ROOT:-/root/owb-workspaces}"
export PATH="$HOME/.local/bin:$PATH"

case "${1:-}" in
  setup)
    command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
    rm -rf "$BENCH_DIR" && git clone -q https://github.com/different-ai/openwork-bench "$BENCH_DIR"
    git -C "$BENCH_DIR" checkout -q "$2"
    cd "$BENCH_DIR" && uv sync --all-extras -q && uv run owb validate | tail -1 && uv run owb models verify | tail -1
    ;;
  check)
    cd "$BENCH_DIR" && uv run owb openwork check --openwork-cdp "$CDP" --workspace-root "$WS_ROOT"
    ;;
  stage)
    spec="$2"; stage="$3"
    test -f "${OPENROUTER_API_KEY_FILE:-/nonexistent}" || { echo "OPENROUTER_API_KEY_FILE not set to a file" >&2; exit 2; }
    cd "$BENCH_DIR"
    uv run python - "$spec" "$stage" <<'PY' > /tmp/owb-stage.sh
import sys, yaml
spec = yaml.safe_load(open(sys.argv[1])); stage = next(s for s in spec["stages"] if s["name"] == sys.argv[2])
from openwork_bench.world_plan import plan
p = plan({**spec, "bench": {**spec["bench"], **{k: v for k, v in stage.items() if k in ("tasks", "repeats", "models")}}, "stages": None})
desk = [r["subject"] for r in p["subjects"] if r["harness"] == "openwork-desktop"]
ctrl = [r["subject"] for r in p["subjects"] if r["harness"] != "openwork-desktop"]
tasks, reps, par = stage.get("tasks", "all"), stage.get("repeats", 3), spec["bench"].get("parallel_sessions", 1)
print(f"uv run owb run {' '.join(desk)} --tasks {tasks} --repeats {reps} --openwork-cdp $CDP --workspace-root $WS_ROOT --workers {par} --out runs/{sys.argv[2]}")
if ctrl: print(f"uv run owb run {' '.join(ctrl)} --tasks {tasks} --repeats {reps} --out runs/{sys.argv[2]}")
PY
    CDP="$CDP" WS_ROOT="$WS_ROOT" bash -euo pipefail /tmp/owb-stage.sh
    uv run owb leaderboard --runs "runs/$stage" --out "runs/$stage/leaderboard.json" | tail -20
    ;;
  *) sed -n '2,6p' "$0"; exit 2 ;;
esac
