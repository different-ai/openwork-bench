from conftest import ROOT
from openwork_bench.world_plan import load_world_spec, plan


def test_world_plan_selects_board_and_prices_it():
    p = plan(load_world_spec(ROOT / "worlds" / "openwork-bench.world.yaml"), ROOT / "tasks")
    ids = {r["subject"] for r in p["subjects"]}
    assert "glm-5.3@openwork-desktop" in ids and "glm-5.3@owb-agent" in ids
    assert "claude-opus-5-5@openwork-desktop" in ids  # closed anchor, same harness
    assert p["totals"]["runs"] == len(p["subjects"]) * p["tasks"] * p["repeats"]
    assert p["totals"]["est_model_usd"] > 0 and p["totals"]["est_sandbox_hours"] > 0
    assert p["problems"] == []  # weights verified in the committed lock file, within budget
    assert any("pnpm world up preview-desktop" in s for s in p["steps"])
    assert any("pnpm world down" in s for s in p["steps"])
