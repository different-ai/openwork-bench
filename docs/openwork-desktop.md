# Running in OpenWork Desktop

The primary board runs every task through **OpenWork Desktop inside an OpenWork world sandbox**:
the real app, server and engine, the same way OpenWork's own end-to-end automation runs. This
document is the run standard.

## The pieces

| Piece | What it is | Where |
|---|---|---|
| World spec | One YAML file describing a complete run: OpenWork build and placement, board, harnesses, repeats, secrets by name, budget | `worlds/openwork-bench.world.yaml` |
| OpenWork world | A sandbox running OpenWork Desktop (server + engine), created with OpenWork's world CLI | `different-ai/openwork`: `pnpm world up preview-desktop --place daytona` |
| Task world | The task's simulated company served as a remote MCP server (streamable HTTP) | `owb world serve <task> --http` (started automatically per attempt) |
| Harness | `openwork-desktop`: drives the OpenWork server for each attempt and reads the result | `src/openwork_bench/harness/openwork_desktop.py` |
| Plan | Checks the spec and prices the run before anything starts | `owb world plan` |

## One attempt, step by step

For each `(model, task, repeat)` the harness:

1. Starts the task world as an MCP server on a free port and keeps its state in memory.
2. Creates a fresh workspace: `POST /workspaces/local` (host token). Nothing from the benchmark
   repository is in it, so the agent cannot read references or checks.
3. Configures the workspace: `PATCH /workspace/:id/config` with
   - the model (`provider` block; OpenRouter routing pinned: no fallbacks, bf16/fp8, no data collection),
   - the task world as a remote MCP server (`mcp.owb-world`, `type: remote`),
   - permissions that deny local edit, shell, web fetch and outside directories, so the agent works
     only through the company tools, exactly like every other subject;

   then `POST /workspace/:id/engine/reload`.
4. Opens a session and sends the task: `POST /workspace/:id/opencode/session`, then
   `POST …/session/:sid/prompt_async` with the shared work context (role, date, rules) followed by
   the brief, and the model id.
5. Polls `GET …/session/status` until the session is idle. Over the step or time budget, it calls
   `POST …/session/:sid/abort`.
6. Reads `GET …/session/:sid/message` and every child session (sub-agents) to sum tokens and the
   engine-reported cost. Main-session-only accounting under-counts sub-agent work.
7. Grades the task world's final state with the same checks as every other harness.

Routes are those of `different-ai/openwork` `dev@915207cb` (`apps/server/src/server.ts`,
`routes/workspaces.ts`, `routes/operations.ts`). Authentication: client routes take
`Authorization: Bearer $OPENWORK_TOKEN`; host routes take `X-OpenWork-Host-Token: $OPENWORK_HOST_TOKEN`.

## Running it

```bash
uv run owb world plan                    # check the spec, list subjects, estimate spend and sandbox hours
```

The plan prints the exact steps. In short:

1. In `different-ai/openwork`: `pnpm world plan preview-desktop --place daytona`, then
   `pnpm world up preview-desktop --place daytona -- --ref <sha> --lifetime 240`.
2. In the sandbox: install `openwork-bench` at a pinned revision, run `owb models verify` and
   `owb validate`, then `owb run <subjects> --openwork-url http://127.0.0.1:8787 --workspace-root …`.
3. Run the control harness (`owb-agent`) for the same models from anywhere.
4. Build the leaderboard, push runs to Hugging Face as a pull request, and `pnpm world down`.

Against an OpenWork you already have running, the same harness works with `--openwork-url`.

## Rules for official runs

- **Pinned everything.** OpenWork revision, openwork-bench revision, weights revisions (lock file)
  and serving settings are recorded in each run manifest.
- **Dedicated, capped model key.** The model key used inside the sandbox is created for the run
  with a spend cap and revoked afterwards. Personal or long-lived keys never enter a sandbox.
- **Spend is approved before `world up`.** `owb world plan` must show no problems and fit the
  budget in the spec; the operator confirms the estimate before provisioning.
- **Always tear down.** Daytona sandboxes do not stop on their own.
- **Same surface for everyone.** Every subject, in either harness, gets the same tools, work
  context, budgets and grading.
- **Infrastructure failures are not scores.** Rows with `status: error` are excluded and re-run.

## Upstream integration

The harness talks to OpenWork's public server routes, so it needs no OpenWork changes. Two
upstream additions would make runs one command and add UI-level evidence:

1. An `openwork-bench` world definition in `different-ai/openwork` `worlds/` that boots
   `preview-desktop`, installs `openwork-bench` and exposes the server to the runner.
2. An evals proof that drives the composer for a sample of attempts with `@openwork/testkit`
   (`agent.send`, `probe.eventually`) and records screenshots, so the published board links to
   footage of real runs in the app.
