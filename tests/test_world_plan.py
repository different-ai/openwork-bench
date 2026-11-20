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


def test_staged_pilot_plan_sums_stages_and_selects_models():
    p = plan(load_world_spec(ROOT / "worlds" / "pilot.world.yaml"), ROOT / "tasks")
    names = [st["stage"]["name"] for st in p["stages"]]
    assert names == ["smoke", "pilot"]
    smoke, pilot = p["stages"]
    assert smoke["tasks"] == 1 and smoke["repeats"] == 1 and pilot["tasks"] == 12 and pilot["repeats"] == 3
    keys = {r["subject"].split("@")[0] for r in pilot["subjects"]}
    assert keys == {"kimi-k3.1-pro", "glm-5.3", "deepseek-v4.1-flash", "qwen3.8-27b", "claude-opus-5-5"}
    assert p["totals"]["runs"] == smoke["totals"]["runs"] + pilot["totals"]["runs"]
    assert p["problems"] == [] and p["totals"]["est_model_usd"] <= p["budget"]["max_model_usd"]
