# The open-weight board

OpenWork Bench's headline board ranks **open-weight models doing knowledge work inside OpenWork**.
The point is to show, with numbers anyone can reproduce, which open models are ready for real
office work and what they cost. That only works if every result is legitimate. These are the rules.

## 1. Only verified open weights

`models/open-weights.yaml` lists the board. `owb models verify` checks each entry on Hugging Face
and writes `models/open-weights.lock.json`:

- the repository is public;
- it contains weight files (`.safetensors`, `.gguf`, `.bin`);
- it declares a license (recorded verbatim; `other` means a custom license, linked from the board);
- the exact revision (commit sha) is pinned.

A model whose weights are announced but not downloadable does not appear on the board. Every run
row records the pinned revision (`open_weights_revision`).

## 2. Known serving, no silent substitution

Open models are served many ways, and results differ by provider and quantization. Each subject
declares how it is served:

| mode | how | when |
|---|---|---|
| `hosted` | OpenRouter with routing pinned: `allow_fallbacks: false`, allowed `quantizations` (bf16, fp8), optional provider `order`, `data_collection: deny` | default for the public board |
| `self-hosted` | vLLM or SGLang in a GPU sandbox loading the pinned revision at a declared precision | reference runs, disputes, models without a trusted host |

Each call records which upstream provider served it (`served_by`) and the billed cost the router
reports (`cost_source: billed`). A run served by a provider outside the subject's allowed list is
voided.

## 3. Same harness, same budgets

The board's primary harness is **OpenWork Desktop** running inside an OpenWork world sandbox
([openwork-desktop.md](openwork-desktop.md)). Every model gets the same app version, the same tools
(the task's MCP world), the same step, token and time budgets, and the model card's recommended
sampling settings. The neutral `owb-agent` harness runs the same models as a control, so the
board can show how much the harness itself adds.

## 4. Clear targets for knowledge work

Scores are placed against fixed targets defined in the index (`targets:` in `index/v0.1.yaml`).
Targets are labels only; they never change a score.

| Level | Index | Solved on every repeat (pass^k) | Unsafe attempts | Every category | Meaning |
|---|---|---|---|---|---|
| **Delegable** | ≥ 80 | ≥ 60% of tasks | ≤ 1% | ≥ 60 | Hand over this kind of work and spot-check it |
| **Ready with review** | ≥ 60 | ≥ 25% of tasks | ≤ 5% | – | Saves real time; a person checks every result |
| **Not ready** | below | | | | Below the bar for reviewed use |

A subject must have run every task to earn a level. Per-category target: 70.

## 5. Closed anchors, clearly marked

One or two closed frontier models (for example Claude Opus 5.5) run through the same harness as
**anchors**, shown greyed and labelled "closed, for reference", so readers can see the gap. They
never take a rank on the open board.

## 6. Reproduce it

```bash
uv run owb models verify                                  # re-check weights, licenses, revisions
uv run owb run glm-5.3@owb-agent --tasks all --repeats 3  # control harness, needs OPENROUTER_API_KEY
uv run owb world plan                                     # check and price the OpenWork world run
```

Results land on Hugging Face with the manifest that names the weights revision, serving mode,
provider, harness version and code revision.
