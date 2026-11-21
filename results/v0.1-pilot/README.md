# v0.1 pilot

The first runs on real models: four open-weight models (Kimi K3.1 Pro, GLM-5.3, DeepSeek V4.1
Flash, Qwen3.8 27B) on the 12 sample tasks, three repeats each, in two harnesses:

- `@openwork-desktop`: OpenWork Desktop in an isolated sandbox, with the task's tools attached
  over MCP.
- `@owb-agent`: the same models in a plain tool-calling loop.

Models are served through OpenRouter with fallbacks off, bf16 or fp8 only, and no data
collection. In the agent app the engine uses the app's own OpenRouter provider, which does not
take these routing options; the served provider is recorded on each row where it is reported.

Each folder is one run: `manifest.json` (subject, revisions, settings), `results.jsonl` (one
graded row per attempt) and `trajectories/` (every message and tool call). Costs are what
OpenRouter billed.

The sample tasks turned out to be easy for current models, so scores cluster near the top.
They prove the pipeline; a harder task set is needed to separate models.
