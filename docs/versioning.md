# Versioning, revisions and corrections

OpenWork Bench is built to be corrected in public without ever rewriting published history.
GitHub and Hugging Face are both git, so every number on the leaderboard can name the exact
commit of code, tasks and results that produced it.

## What is versioned, and where

| Thing | Version | Lives in | Changes by |
|---|---|---|---|
| Engine code | git commit (`code_revision` in each run manifest) | GitHub | PR |
| A task | `version:` integer in task.yaml + content `fingerprint` | GitHub `tasks/` | PR |
| Task suite release | tag `tasks-vX.Y.Z` | GitHub tag + Hugging Face dataset tag | release |
| Graders | `GRADER_VERSION` in code, stored on every row | GitHub | PR |
| Index definition | `index/vX.Y.yaml` (splits, weights, scoring, repeats) | GitHub | PR, new file |
| Prices | `pricing.yaml` entries with `effective` date | GitHub | PR |
| Runs | immutable `run_id` folder | Hugging Face results dataset | Hub PR |
| Corrections | `errata/E-NNNN.yaml` | GitHub | PR |
| Official leaderboard | `leaderboard/published.yaml` pin → HF results revision | GitHub | PR |

## The flows

### Add results
1. `owb run <subject>` writes `runs/<run_id>/` with manifest, results and trajectories.
2. `owb hub push-run runs/<run_id>` opens a **pull request on the Hugging Face results dataset**.
3. A maintainer reviews (manifest revisions, error rate, spot-check trajectories) and merges.
4. To publish: a GitHub PR updates `leaderboard/published.yaml` to the merged HF revision; CI
   rebuilds the site from exactly that revision.

### Fix a task (wrong expected value, ambiguous brief)
1. PR edits the task and **bumps `version`**; CI re-validates (oracle 1.0, no-op ≤ 0.15).
2. Add `errata/E-NNNN.yaml` (`type: task-fix`, `affects.tasks: [id@old_version]`, `action: rerun`).
3. Older rows for that task become **stale** automatically and drop out of the index until
   subjects are re-run on the new version.

### Fix a grader
1. PR fixes the check logic and bumps `GRADER_VERSION`.
2. `owb regrade runs/<run_id>` re-scores **stored final states**: no agent is re-run, so the fix
   is cheap and exact. Push the regraded runs as a new HF commit (via PR).
3. Errata entry `type: grader-fix`, `action: regrade`.

### Void a bad run (provider outage, harness bug)
Errata entry `action: void` with the run ids. The leaderboard builder drops them; the data stays
on Hugging Face for audit.

### Change prices
Add a new `pricing.yaml` entry with an `effective` date. Costs are recomputed from stored token
counts, so no re-runs are needed.

### Change weights, scoring or the task set
Create a new index version (`index/v0.2.yaml`). Old versions stay, so old leaderboards remain
reproducible. Rows carry their `index_version`; the builder only mixes versions when asked
(`--any-index`).

## Reproducing a published row

```bash
git checkout <code_revision from the run manifest>
uv run owb hub pull-results --revision <results_revision from leaderboard/published.yaml>
uv run owb leaderboard --runs hub-results --index v0.1
uv run owb run <subject> --tasks <task>     # re-run it yourself with your own keys
```
