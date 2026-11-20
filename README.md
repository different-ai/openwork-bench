# OpenWork Bench

**Which open models can you trust with real knowledge work, and at what cost, speed and risk?**

OpenWork Bench is an open, reproducible benchmark and leaderboard for AI agents doing knowledge
work. Its headline board ranks **open-weight models running real office tasks inside OpenWork**,
with one index, quality plotted against cost and speed, confidence intervals, and clear readiness
targets: *Delegable*, *Ready with review* or *Not ready*.

- **Real workplace tasks.** Agents work inside a simulated company with email, calendar, files,
  CRM, chat and a directory. They draft memos, reconcile invoices, reschedule meetings, triage
  inboxes, update deals and plan projects.
- **Graded on outcomes and side effects.** Deterministic checks read the final state: the right
  email went to the right people, the numbers in the spreadsheet are right, nothing was deleted,
  nothing leaked to an outside address. An unsafe attempt scores 0.
- **Open-weight models, legitimately.** Every model's weights are verified on Hugging Face and
  pinned to a revision; serving providers and precision are pinned and recorded per call.
- **Run in OpenWork.** Each task runs in OpenWork Desktop inside an OpenWork world sandbox, with a
  neutral control harness alongside to show what the model does on its own.
- **Everything is open.** Tasks, worlds, harness, graders, every run's full trajectory, and the
  method that turns them into a score. Code on GitHub, data on Hugging Face, both versioned.

> Status: **preview.** 12 sample tasks across six categories, a verified catalog of 12 open-weight
> models, the OpenWork Desktop world runner, offline reference and simulated subjects, MCP world
> server, leaderboard site and Hugging Face publishing. No official results are published yet.

## Quick start

```bash
git clone https://github.com/different-ai/openwork-bench && cd openwork-bench
uv sync --all-extras          # or: pip install -e ".[all,dev]"
uv run owb validate           # every task: solvable by its reference, ~0 for an empty answer
uv run owb demo --open        # offline: run reference + simulated subjects, build the site
```

`owb demo` needs no API keys. It runs an oracle, a no-op and four *simulated* agents (seeded
test agents with made-up cost and speed, clearly labelled) through every task three times, builds
`runs-demo/leaderboard.json` and opens `site/dist/index.html`.

### Run an open-weight model

```bash
uv run owb models verify                       # check weights, licenses and revisions on Hugging Face
export OPENROUTER_API_KEY=...
uv run owb run glm-5.3@owb-agent --tasks all --repeats 3      # control harness
uv run owb world plan --world worlds/openwork-bench.world.yaml # the OpenWork Desktop run, priced first
uv run owb leaderboard --runs runs runs-demo && uv run owb site --open
```

Running models costs money. `owb world plan` prints the run matrix, estimated tokens, cost and
sandbox hours before anything starts. See [docs/openwork-desktop.md](docs/openwork-desktop.md).

### Explore

```bash
uv run owb tasks                                   # list tasks
uv run owb subjects                                # list subjects
uv run owb show runs-demo/<run_id>                 # per-task scores of a run
uv run owb show runs-demo/<run_id> --task inbox-triage --repeat 1   # one trajectory
```

### Test an agent product (OpenWork, Claude Code, Codex, ...)

Every task's workplace is also an MCP server. Point any agent at it, give it the brief, grade the
end state:

```bash
uv run owb world serve inbox-triage --state-out state.json   # MCP over stdio
uv run owb grade-state inbox-triage state.json
```

See [docs/harness-adapters.md](docs/harness-adapters.md).

## How scoring works

| | |
|---|---|
| **OpenWork Bench Index** | Equal-weighted mean of six categories, 0–100, with a 95% bootstrap CI |
| **Categories** | Research & analysis · Documents & writing · Spreadsheets & data · Communication & coordination · Multi-app operations · Long-horizon projects |
| **Task score** | Weighted share of checks passed; a failed *critical* check caps it at 25%; a safety violation makes it 0 |
| **Reliability** | pass@1 and pass^k (solved on every one of k repeats) |
| **Safety** | Share of attempts that deleted without being asked, emailed unknown outside addresses, or crossed a task's red line |
| **Cost, time, tokens** | Metered per attempt; cost from `pricing.yaml` list prices |
| **Value** | Expert labour cost of the work delivered ÷ agent cost; expert time ÷ agent time |

Full method: [docs/methodology.md](docs/methodology.md).

## Repository map

```
tasks/<category>/<task-id>/   task.yaml · world.yaml · reference.yaml · workspace/   (CC BY 4.0)
tasks/_shared/                shared fictional company (Larkspur Supply Co.)
models/open-weights.yaml      open-weight catalog (+ .lock.json: verified revisions and licenses)
worlds/                       OpenWork world run specs
subjects/                     reference, simulated and closed-anchor subjects
index/v0.1.yaml               index definition: splits, weights, scoring, repeats
pricing.yaml                  list prices for cost per task
errata/                       every correction to published results
leaderboard/published.yaml    pin: which Hugging Face results revision is official
src/openwork_bench/           engine: world, harnesses, providers, graders, index, site, hub
docs/                         plan, methodology, task format, versioning, data, adapters
```

## Docs

- [Design and roadmap](docs/PLAN.md)
- [The open-weight board](docs/open-weights.md)
- [Running in OpenWork Desktop](docs/openwork-desktop.md)
- [Methodology](docs/methodology.md)
- [Writing tasks](docs/task-format.md)
- [Versioning, revisions and corrections](docs/versioning.md)
- [Data on Hugging Face](docs/data-on-hugging-face.md)
- [Harness adapters and agent products](docs/harness-adapters.md)
- [Fair play](docs/fair-play.md): OpenWork maintains this benchmark and appears on it; these rules keep it honest.

## Contributing

New tasks from working professionals are the most valuable contribution. See
[CONTRIBUTING.md](CONTRIBUTING.md). Commits need a DCO sign-off (`git commit -s`).

## License

Code: [Apache-2.0](LICENSE). Tasks and published data: [CC BY 4.0](LICENSE-DATA). Please do not
train models on the tasks: every task carries an `OWB-CANARY-` string.
