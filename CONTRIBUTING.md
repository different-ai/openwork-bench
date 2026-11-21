# Contributing to OpenWork Bench

Thanks for helping build an honest measure of AI knowledge work.

## What helps most

1. **Tasks from people who do the work.** Accountants, analysts, assistants, recruiters,
   salespeople, operations staff: a task drawn from your real job (with every detail made
   fictional) is worth more than anything else. See [docs/task-format.md](docs/task-format.md).
2. **Fixes to tasks and graders.** If a check rejects a correct answer or accepts a wrong one,
   open an issue or PR. Fixes bump the task version and get an errata entry.
3. **Harness adapters** for agent products. See [docs/harness-adapters.md](docs/harness-adapters.md).
4. **Vendor submissions.** If you build an agent, you may submit or fix your own adapter. See
   [docs/fair-play.md](docs/fair-play.md).

## Development

```bash
uv sync --all-extras
uv run ruff check src tests && uv run ruff format --check src tests
uv run pytest
uv run owb validate
```

## Pull requests

- Open PRs against `pre-release` (`--base pre-release`); `main` takes only release PRs from
  `pre-release`. See [docs/maintaining.md](docs/maintaining.md).
- One focused change per PR, with a plain description of the problem and the change.
- New or changed tasks must pass `owb validate`: the reference solution scores 1.0 and an empty
  submission scores at most 0.15.
- Changing a published task: bump its `version`, add an `errata/` entry, never reuse an id.
- Changing scoring or weights: propose a new `index/` version; existing versions stay untouched.

## Developer Certificate of Origin

Every commit must be signed off, certifying the [DCO](https://developercertificate.org/):

```bash
git commit -s -m "feat(tasks): add a payroll-correction task"
```

## Data rules

- Everything in a task is fictional. Use the `.example` domain for addresses.
- No real customer, employee or company data, no credentials, no copyrighted documents.
- Keep the task's `OWB-CANARY-` string.
