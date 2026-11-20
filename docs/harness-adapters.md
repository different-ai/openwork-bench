# Harness adapters and agent products

## Built in

| kind | What it is |
|---|---|
| `openwork-desktop` | OpenWork Desktop's server and engine in an OpenWork world sandbox, with the task world attached over MCP ([openwork-desktop.md](openwork-desktop.md)) |
| `agent` (`harness: owb-agent`) | Neutral tool loop over a model provider: `anthropic` (official SDK) or `openai` (any Chat Completions endpoint) |
| `scripted` | Replays `reference.yaml` (oracle) |
| `noop` | Submits nothing |
| `simulated` | Seeded test agent with simulated cost/time; offline pipeline tests only |

Add an open-weight model: an entry in `models/open-weights.yaml`, then `owb models verify`. It
becomes one subject per harness (`<key>@openwork-desktop`, `<key>@owb-agent`). Other models: a
YAML file in `subjects/` (see `claude-*.yaml` and `openai-compatible.example.yaml.txt`). Set
`family` so judges from the same vendor are excluded.

## Agent products over MCP

Each task's world is exposed as an MCP server (stdio by default):

```bash
uv run owb world serve <task-id> --state-out state.json
```

Add `--http --port 8765` to serve over streamable HTTP for agents that attach remote servers.

Manual run with any MCP-capable agent (Claude Code, Codex, Cursor...):

1. Register the command above as an MCP server in the product.
2. Give the agent the task brief (`owb tasks`, or the server instructions) and tell it to call
   `submit` when done.
3. Grade: `uv run owb grade-state <task-id> state.json`.

### Automated product adapters

OpenWork Desktop is automated today (`openwork-desktop`). Other products follow the same pattern.

A product adapter is a subject with `kind: external` and a command template. The runner will:

1. start the world MCP server for the task (stdio or streamable HTTP);
2. launch the product headlessly with the server attached and the brief as its prompt;
3. wait for `submit`, the budget, or the process to exit;
4. read the world snapshot and grade it like any other row; record the product's own usage and
   cost when it reports them.

Rules: the adapter, its config and the exact product version are public; the product gets the
same task budgets as everyone else; vendors may submit or fix their own adapter
([fair-play.md](fair-play.md)).
