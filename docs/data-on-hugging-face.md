# Data on Hugging Face

| Dataset | Contents | Updated by |
|---|---|---|
| `different-ai/openwork-bench-tasks` | `tasks.jsonl` (one row per task: brief, world, checks, rubric, reference, metadata) and `files/<task_id>/...` workspace files. Tagged per suite release (`tasks-v0.1.0`). Private split excluded. | `owb hub push-tasks --tag tasks-vX.Y.Z` on release (CI on tag) |
| `different-ai/openwork-bench-results` | `runs/<index_version>/<run_id>/manifest.json`, `results.jsonl`, `trajectories/*.json`; `leaderboards/<index_version>/<date>.json` | `owb hub push-run` (opens a Hub pull request); `owb hub publish-leaderboard` |
| `different-ai/openwork-bench-tasks-private` (planned, private) | held-out split | maintainers only |

The namespace defaults to `different-ai`; override with `OWB_HF_NAMESPACE` or `--repo`.

## Why Hugging Face for data

- Runs are large (full trajectories and final world states) and append-only; Git LFS-backed
  datasets handle that better than the code repo.
- The dataset viewer shows `results.jsonl` across all runs as one table (`configs` in the card),
  so anyone can slice results without cloning.
- Hub pull requests give review for result submissions; commits and tags give exact revisions to
  pin; nothing needs to be rewritten to correct it.

## Commands

```bash
export HF_TOKEN=...                      # a token with write access to the namespace
uv run owb hub export-tasks --out dist/hf-tasks          # local, no network: inspect first
uv run owb hub push-tasks --tag tasks-v0.1.0             # publish + tag a suite release
uv run owb hub push-run runs/<run_id>                    # opens a Hub PR on the results dataset
uv run owb hub push-run runs/<run_id> --direct           # maintainers: commit directly
uv run owb hub pull-results --revision <sha-or-tag>      # results only (add --trajectories for all)
uv run owb hub publish-leaderboard runs/leaderboard.json --tag lb-v0.1-2026-12-01
```

## Row schema (`results.jsonl`)

`run_id, index_version, subject_id, subject_label, subject_type, model, harness, task_id,
task_version, task_fingerprint, category, split, repeat, status, error, score, success,
critical_failed, safety_violation, checks[], safety[], rubric[], rubric_status, usage{},
cost_usd, wall_s, steps, turns, simulated, grader_version, started_at`

## Privacy

Published runs contain only the fictional world and the agent's actions. Run manifests store the
subject's public config (no keys) and the code revision, not host names or user identities.
