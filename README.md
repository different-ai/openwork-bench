# OpenWork Bench

**Which AI agents do real knowledge work best, and at what cost, speed and risk?**

OpenWork Bench is an open, reproducible benchmark and leaderboard for AI agents doing
knowledge work. It is modelled on [Artificial Analysis](https://artificialanalysis.ai): one
headline index, quality plotted against cost and speed, versioned methodology, confidence
intervals. It is built for office work rather than exams:

- **Real workplace tasks.** Agents work inside a simulated company with email, calendar, files,
  CRM, chat and a directory. They draft memos, reconcile invoices, reschedule meetings, triage
  inboxes, update deals and plan projects.
- **Graded on outcomes and side effects.** Deterministic checks read the final state: the right
  email went to the right people, the numbers in the spreadsheet are right, nothing was deleted,
  nothing leaked to an outside address. An unsafe attempt scores 0.
- **Scores the agent system, not only the model.** A subject is `model × harness`. Compare models
  through the neutral built-in harness, or connect any agent product over MCP.
- **Everything is open.** Tasks, worlds, harness, graders, every run's full trajectory, and the
  method that turns them into a score. Code on GitHub, data on Hugging Face, both versioned.

> Status: **v0.1 preview.** 12 sample tasks across all six categories, offline reference and
> simulated subjects, Claude and OpenAI-compatible model adapters, MCP world server, leaderboard
> site, Hugging Face publishing. No official model results are published yet.

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

### Run a real model

```bash
export ANTHROPIC_API_KEY=...          # or `ant auth login`
uv run owb run claude-sonnet-5-5 --tasks all --repeats 3
uv run owb leaderboard --runs runs runs-demo
uv run owb site --open
```

Any OpenAI-compatible endpoint works too: copy `subjects/openai-compatible.example.yaml.txt` to
`subjects/<id>.yaml`. Running models costs money: a full v0.1 pass is 12 tasks × 3 repeats.

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
subjects/                     what gets scored: model × harness configs
index/v0.1.yaml               index definition: splits, weights, scoring, repeats
pricing.yaml                  list prices for cost per task
errata/                       every correction to published results
leaderboard/published.yaml    pin: which Hugging Face results revision is official
src/openwork_bench/           engine: world, harnesses, providers, graders, index, site, hub
docs/                         plan, methodology, task format, versioning, data, adapters
```

## Docs

- [Plan and roadmap](docs/PLAN.md)
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
