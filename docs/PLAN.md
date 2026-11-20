# OpenWork Bench — design and roadmap

This document describes what OpenWork Bench measures, how it is built, and where it is going.
The other documents describe how each part works today.

## 1. Purpose

Teams adopting AI for office work need to know which agent setup will actually do the job, what
it costs, how long it takes, and whether it can be trusted not to cause damage. OpenWork Bench
answers that for **open-weight models doing knowledge work**, with results anyone can reproduce.

| Related benchmarks | Strength | What OpenWork Bench adds |
|---|---|---|
| GDPval | Expert-written deliverables across 44 occupations | Tool use, side effects, cost and safety on every task |
| APEX-Agents, TheAgentCompany, Workspace-Bench, OfficeBench | Long-horizon, multi-app agent tasks | Cost, reliability and safety as first-class scores; fully open data |
| τ-bench, OSWorld | Reliability (pass^k), policy adherence, computer use | An office-work suite with readiness targets |

### Focus: open models you can trust with work

The headline board ranks open-weight models on real office tasks and gives each a verdict:
Delegable, Ready with review or Not ready. It shows how far downloadable, self-hostable models go
for knowledge work, and what they cost. Tasks run in a real desktop agent app (OpenWork) inside
isolated sandboxes, with a plain tool loop alongside as a control. Results follow strict rules: verified weights pinned to a revision,
pinned serving and precision, identical harness and budgets, a neutral control harness, closed
models shown only as labelled anchors, and fixed readiness targets
([open-weights.md](open-weights.md), [openwork-desktop.md](openwork-desktop.md)).

OpenWork maintains the benchmark. Because OpenWork also appears on it, the rules in
[fair-play.md](fair-play.md) are part of the product.

## 2. Principles

1. **Open by default.** Code, public tasks, graders, full run logs and the scoring method are
   public. Only the held-out split is withheld; its size and schedule are public.
2. **Outcomes over transcripts.** Grade the end state of the workplace, not how the agent talked.
3. **Deterministic first.** Exact state checks wherever possible; model judges only for qualities
   checks cannot capture, with published agreement against human experts.
4. **Every number is reproducible.** Each score points at exact revisions of code, tasks, weights
   and results.
5. **Corrections are additive.** Fixes are new versions, regrades and errata. Nothing published is
   rewritten.
6. **The whole picture.** Quality, cost, time, reliability and safety together, with uncertainty
   on every score and a clear readiness target.

## 3. What is measured

### 3.1 Subjects

A subject is `model × harness`.

| Type | Example | Harness |
|---|---|---|
| `product` | GLM-5.3 in OpenWork Desktop | OpenWork Desktop in a world sandbox (primary board) |
| `model` | GLM-5.3 in `owb-agent` | the neutral built-in tool loop (control) |
| `reference` | oracle, no-op | scripted; prove tasks are solvable and graders not gameable |
| `simulated` | seeded test agents | offline pipeline tests; never on official boards |

### 3.2 Categories

| Category | Typical work |
|---|---|
| Research & analysis | Find, compare and synthesise across documents; answer from policy |
| Documents & writing | Memos, proposals, summaries from notes and templates |
| Spreadsheets & data | Reconcile, aggregate, compute variances, produce tables |
| Communication & coordination | Triage, reply, schedule, coordinate people |
| Multi-app operations | Update systems of record from conversations; cross-tool workflows |
| Long-horizon projects | Multi-part projects combining all of the above |

### 3.3 Metrics and targets

- **OpenWork Bench Index** (0–100), category scores, per-task scores, 95% bootstrap CI.
- **pass@1** and **pass^k** (solved on every one of k repeats).
- **Unsafe attempt rate** (global rules plus task red lines).
- **Cost, time, tokens and steps per task**; billed cost where the provider reports it.
- **Value per dollar** and **speed-up** against per-task expert baselines.
- **Readiness:** *Delegable*, *Ready with review* or *Not ready*, from fixed thresholds on the
  index, pass^k, unsafe rate and the weakest category.

### 3.4 Presentation

Index chart with readiness lines · time per task · cost per task · index vs cost · category table ·
reliability and safety · per-task heatmap · full results table · changelog of index versions and
errata.

## 4. Architecture

```
            ┌──────────────── GitHub (review) ────────────────┐
            │ tasks/  models/  index/  pricing.yaml  errata/   │
            │ worlds/  subjects/  src/  leaderboard/published  │
            └──────┬──────────────────────────────▲───────────┘
   owb hub push-tasks (tag)                       │ PR updates the pin
            ▼                                     │
  HF dataset: openwork-bench-tasks      HF dataset: openwork-bench-results
                                        runs/<index>/<run_id>/{manifest, results, trajectories}
            │                                     ▲
            ▼                                     │ owb hub push-run (Hub PR)
   OpenWork world sandbox ── OpenWork Desktop ── open-weight model (pinned serving)
            │                       │
            └── task MCP world ◄────┘ tools ──► final state ──► grade ──► run folder
```

Engine modules (`src/openwork_bench/`): `world` (simulated workplace), `mcp_server` (the world over
MCP, stdio or HTTP), `harness/` (OpenWork Desktop driver, `owb-agent`, scripted), `providers/`,
`grading/`, `runner`, `index`, `models` (catalog and weight verification), `site/`, `hub`,
`validate`, `world_plan`.

GitHub holds what people review: tasks, method, catalog, corrections and the pin to the official
results revision. Hugging Face holds what is large and append-only: published tasks, every run's
results and trajectories, and leaderboard snapshots. Both are git, so every number names a commit
on each side ([data-on-hugging-face.md](data-on-hugging-face.md), [versioning.md](versioning.md)).

## 5. Roadmap

### v0.1 — the loop
- 12 sample tasks across six categories; `owb validate` (reference = 1.0, empty ≤ 0.15).
- `owb-agent` with Claude and OpenAI-compatible providers; MCP world server.
- Deterministic checks, global safety rules, judge panel, bootstrap CIs; static site;
  Hugging Face publishing; errata, regrade and pinning; CI.

### v0.1.1 — open-weight board in OpenWork
- Open-weight catalog verified against Hugging Face; revisions and licenses pinned.
- Pinned OpenRouter routing (no fallbacks, bf16/fp8, no data collection); billed cost and serving
  provider recorded per call.
- `openwork-desktop` harness and the world run standard (`worlds/`, `owb world plan`).
- Readiness targets on the index and site.
- **Done when:** one open model completes the sample suite through OpenWork in a world, producing
  the same rows and manifest as the control harness.

### v0.2 — first public board
- 60 tasks (10 per category) across ~15 occupations and 2–3 fictional companies.
- Measured expert baselines from timed professionals.
- Judge calibration: ~200 human-labelled rubric items; per-rubric-type agreement published.
- Board: the open-weight catalog through OpenWork Desktop, the same models through `owb-agent`,
  1–2 closed anchors.
- Held-out split (≈30% of tasks) run identically for every subject.

### v0.3 — breadth and trust
- 150 tasks, 30 occupations; multi-turn tasks with a simulated colleague; ambiguous briefs that
  reward asking.
- Self-hosted reference serving (vLLM/SGLang in GPU sandboxes) for disputes and new models.
- Pairwise preference ratings for open-ended deliverables; independent reviewer for index versions.

### v1.0 — the index
- 300+ tasks with quarterly releases and held-out rotation; per-occupation boards; index history;
  real office file formats (xlsx, docx, pdf) and larger multi-week worlds.

## 6. Task program

- **Authors:** practising professionals write tasks from their real work with every detail made
  fictional; maintainers review against [task-format.md](task-format.md).
- **Coverage:** occupations weighted by US knowledge-work employment (O*NET/SOC), balanced across
  the six categories.
- **Quality bar:** a reference solution, critical checks, at least one trap (stale document, decoy
  record, phishing, partial payment), and outcome-validity checks.
- **Splits:** `public-dev`, `public-test`, `private` (held-out, rotates into public on retirement).

## 7. Cost to run

A full pass is `tasks × repeats` runs per subject. `owb world plan` estimates tokens, cost and
sandbox hours before anything starts. Task budgets cap steps, tokens and time for every subject.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Maintainer also appears on the board | Public adapters, equal budgets, control harness, vendor submissions, published losses |
| Contamination | Canary strings, held-out split, public-vs-private gap reported |
| Serving differences for open models | Pinned providers and precision, `served_by` per call, self-hosted reference runs |
| Grader bugs | Validation in CI; errata; regrade without re-running agents |
| Judge bias | Deterministic-first; multi-vendor panel; family exclusion; published agreement |
| Simulated worlds too easy | Professional authors, traps, larger worlds and real file formats over time |
| Provider flakiness | Infrastructure errors excluded and re-run; status recorded per row |
