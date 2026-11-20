# Harness adapters and agent products

## Built in

| kind | What it is |
|---|---|
| `agent` (`harness: owb-agent`) | Neutral tool loop over a model provider: `anthropic` (official SDK) or `openai` (any Chat Completions endpoint) |
| `scripted` | Replays `reference.yaml` (oracle) |
| `noop` | Submits nothing |
| `simulated` | Seeded test agent with simulated cost/time; offline pipeline tests only |

Add a model: a YAML file in `subjects/` (see `claude-*.yaml` and
`openai-compatible.example.yaml.txt`). Set `family` so judges from the same vendor are excluded.

## Agent products over MCP

Each task's world is exposed as an MCP server (stdio), with the brief in the server instructions:

```bash
uv run owb world serve <task-id> --state-out state.json
```

Manual run with any MCP-capable agent (OpenWork, Claude Code, Codex, Cursor...):

1. Register the command above as an MCP server in the product.
2. Give the agent the task brief (`owb tasks`, or the server instructions) and tell it to call
   `submit` when done.
3. Grade: `uv run owb grade-state <task-id> state.json`.

### Automated product adapters (v0.2)

A product adapter is a subject with `kind: external` and a command template. The runner will:

1. start the world MCP server for the task (stdio or streamable HTTP);
2. launch the product headlessly with the server attached and the brief as its prompt;
3. wait for `submit`, the budget, or the process to exit;
4. read the world snapshot and grade it like any other row; record the product's own usage and
   cost when it reports them.

Rules: the adapter, its config and the exact product version are public; the product gets the
same task budgets as everyone else; vendors may submit or fix their own adapter
([fair-play.md](fair-play.md)).
