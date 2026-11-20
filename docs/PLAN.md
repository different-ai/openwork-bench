# OpenWork Bench — plan

Status: v0.1 preview (2026-11-20). Owner: OpenWork. This document is the long-range plan; the
other docs describe how things work today.

## 1. Why this exists

Buyers of AI for office work want to know which agent will actually do the job, what it costs,
how long it takes and whether it can be trusted not to do damage. Existing measures leave gaps:

| Existing | What it does well | Gap OpenWork Bench fills |
|---|---|---|
| Artificial Analysis Intelligence Index | Independent runs, one index, cost and speed side by side, versioned methodology | Harness and its knowledge-work tasks (AA-Briefcase) are private; scores models, not agent products |
| GDPval / GDPval-AA | Expert-written deliverables across 44 occupations; pairwise grading vs experts | One-shot deliverables; no tools, no side effects, no cost or safety axis |
| APEX-Agents, TheAgentCompany, Workspace-Bench, OfficeBench | Long-horizon, multi-app agent tasks | Mostly pass rate only; cost, reliability and safety not first-class; some gated |
| τ-bench, OSWorld | pass^k reliability, policy adherence, computer use | Not office-work suites |

OpenWork Bench combines the Artificial Analysis presentation with an open, agentic,
knowledge-work suite that grades both the deliverable and the side effects, and that can
score agent products as well as models.

**Who runs it.** OpenWork maintains OpenWork Bench, in the tradition of company-run benchmarks
such as Mercor's APEX, Scale's Remote Labor Index and Zapier's AutomationBench. The aim is the most
rigorous and most open measure of AI knowledge work. Its credibility has to come from openness and
fair rules ([fair-play.md](fair-play.md)), not from a claim of independence.

## 2. Principles

1. **Open by default.** Code, public tasks, graders, full run logs and the index method are
   public. Only the private held-out split is withheld, and its existence and size are public.
2. **Outcomes over transcripts.** Grade the end state of the workplace, not how the agent talked.
3. **Deterministic first.** Prefer exact state checks; use LLM judges only for qualities that
   checks cannot capture, and publish their agreement with human experts.
4. **Every number is reproducible.** Each published score points at exact revisions of code,
   tasks and results. One command reproduces a public row.
5. **Corrections are additive.** Nothing published is rewritten. Fixes are new versions,
   regrades and errata, reviewed in public.
6. **Report the whole picture.** Quality, cost, time, reliability and safety together; uncertainty
   on every score.

## 3. What is measured

### 3.1 Subjects

A subject is `model × harness`:

| Type | Example | Harness |
|---|---|---|
| `model` | Claude Opus 5.5 | `owb-agent`, the neutral built-in tool loop |
| `product` | OpenWork, Claude Code, Codex, Cursor agents | the product's own agent, connected over MCP |
| `reference` | oracle, no-op | scripted; prove tasks are solvable and graders are not gameable |
| `simulated` | seeded test agents | for offline pipeline testing; never mixed into official boards |

### 3.2 Categories (equal weight in v0.x)

| Category | Typical work |
|---|---|
| Research & analysis | Find, compare and synthesise across documents; answer from policy |
| Documents & writing | Memos, proposals, summaries from notes and templates |
| Spreadsheets & data | Reconcile, aggregate, compute variances, produce tables |
| Communication & coordination | Triage, reply, schedule, coordinate people |
| Multi-app operations | Update systems of record from conversations; cross-tool workflows |
| Long-horizon projects | Multi-part projects combining all of the above |

### 3.3 Metrics

- **Index** (headline), category scores, per-task scores, 95% bootstrap CI.
- **pass@1, pass^k** (k = repeats, 3 in v0.x).
- **Safety violation rate** (global rules + task red lines).
- **Cost per task** (USD), **time per task**, **tokens**, **steps**.
- **Value per dollar** (expert labour cost of delivered work ÷ agent cost) and **speed-up vs
  expert**, using per-task expert baselines.
- Later: **clarification quality** (asks when the brief is truly ambiguous), **calibration**
  (says when it could not finish), **human-preference Elo** on open-ended deliverables.

### 3.4 Charts (the Artificial Analysis set, for knowledge work)

Index bar chart with CIs · Index vs cost (log) · Index vs time (log) · category heat table ·
reliability and safety bars · per-task heatmap · all-results table. Later: per-occupation view,
cost-to-run-the-whole-index, index history over versions.

## 4. Architecture

```
            ┌──────────────── GitHub (review) ────────────────┐
            │ tasks/ (source)  index/  pricing.yaml  errata/   │
            │ subjects/  src/ (engine)  leaderboard/published  │
            └──────┬──────────────────────────────▲───────────┘
   owb hub push-tasks (tag)                       │ PR changes the pin
            ▼                                     │
  HF dataset: openwork-bench-tasks      HF dataset: openwork-bench-results
  (tagged suite releases)               runs/<index>/<run_id>/{manifest, results, trajectories}
            │                           leaderboards/<index>/<date>.json
            ▼                                     ▲
   owb run ──► World (MCP tools) ◄── harness ──► grade ──► run folder ──► owb hub push-run (PR)
                                                                   │
                         owb leaderboard (+ errata, pinned revision) ──► site (GitHub Pages)
```

Engine modules (`src/openwork_bench/`): `world` (simulated workplace + tool registry),
`harness/` (agent loops), `providers/` (Claude via the Anthropic SDK; OpenAI-compatible),
`grading/` (checks, global safety rules, judge panel), `runner` (runs, manifests, regrade),
`index` (leaderboard math), `site/` (static site), `hub` (Hugging Face), `mcp_server`,
`validate` (outcome validity).

Why this split: GitHub is where people review text (tasks, method, corrections); Hugging Face is
where large, append-only data belongs and where the research community already looks. Both are
git, so every published number names a commit on each side. Details:
[data-on-hugging-face.md](data-on-hugging-face.md), [versioning.md](versioning.md).

## 5. Roadmap

### v0.1 — prove the loop (this release)
- 12 sample tasks, 2 per category, one fictional company; validate = oracle 1.0, no-op ≤ 0.15.
- Built-in harness with Claude and OpenAI-compatible providers; MCP world server.
- Deterministic checks, global safety rules, judge panel (off by default), bootstrap CIs.
- Static leaderboard; Hugging Face export/push/pull; errata and pinning; CI.
- **Done when:** `owb demo` runs offline in seconds; tests pass; one real model can be run end to end.

### v0.2 — first real board (target: 4–6 weeks)
- 60 tasks (10 per category) across ~15 occupations, 2–3 fictional companies.
- Expert baselines measured (timed professionals), not author estimates.
- Judge calibration set: ~200 human-labelled rubric items; publish per-rubric-type κ; drop
  rubric types below κ 0.6.
- First official runs: 6–10 frontier and open models through `owb-agent`; OpenWork and 2–3 other
  agent products through MCP adapters, labelled.
- Private held-out split (≈30% of tasks) run by maintainers; public-vs-private gap reported.
- Publish tasks `tasks-v0.2.0` and results to Hugging Face; pin the first official leaderboard.

### v0.3 — breadth and trust
- 150 tasks, 30 occupations; multi-turn tasks with a simulated colleague who answers questions;
  ambiguous briefs that reward asking.
- Pairwise Elo on open-ended deliverables (memos, proposals) with a fixed anchor subject.
- External advisory reviewer signs off on index versions.
- Vendor self-submission flow (adapter PR + maintainer re-run).

### v1.0 — the index
- 300+ tasks, quarterly releases with rotation of the private split.
- Per-occupation leaderboards; index history; cost to run the whole index.
- Larger worlds (thousands of files, multi-week projects) and real file formats (xlsx, docx, pdf).

## 6. Task program

- **Sources:** paid professionals write tasks from their real work, with all details made
  fictional; maintainers review against the checklist in [task-format.md](task-format.md).
- **Coverage plan:** weight occupations by US knowledge-work employment (O*NET/SOC), as GDPval
  does, while keeping six balanced categories for the index.
- **Quality bar:** every task has a reference solution, critical checks, at least one trap (stale
  document, decoy record, phishing, partial payment...), and passes outcome-validity checks.
- **Splits:** `public-dev` (open, for development), `public-test` (open, counts), `private`
  (held-out, counts, run only by maintainers). Private tasks rotate into public on retirement.

## 7. Running costs (planning numbers)

A full pass is `tasks × repeats` agent runs. At v0.2 (60 tasks × 3) that is 180 runs per subject.
At roughly 30–150k tokens per run, a frontier model costs on the order of $10–$100 per subject per
pass; ten subjects ≈ $100–$1,000 per release before judges. Judges add ~10–20% when rubric items are
enabled. Budgets per task are enforced in `task.yaml`.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Conflict of interest (OpenWork runs and appears on the board) | Fair-play rules: public adapters, equal budgets, labelled rows, vendor submissions, publish losses |
| Contamination | Canary strings, private split, report public-vs-private gap |
| Grader bugs (false pass/fail) | Oracle/no-op validation in CI; errata; regrade without re-running |
| LLM-judge bias | Deterministic-first; panel of vendors; family exclusion; published κ |
| Simulated worlds too easy or unrealistic | Professional authors; traps; larger worlds and real file formats from v0.3 |
| Provider flakiness | Infra errors excluded and re-run; status recorded per row |
| Cost of runs | Budgets per task; repeats configurable; batch runs at release only |

## 9. Open decisions

1. GitHub/Hugging Face namespaces (default `different-ai`).
2. Run budget for the first official board.
3. Whether the private split starts at v0.2 (recommended) or v0.3.
4. Which agent products to invite first.
