import json

from openwork_bench.grading.judge import JudgePanel, parse_verdict
from openwork_bench.hub import export_tasks
from openwork_bench.index import build_leaderboard, load_index_config
from openwork_bench.runner import load_rows, run_subject
from openwork_bench.site import build_site
from openwork_bench.subjects import load_subjects
from openwork_bench.world import World


def test_export_tasks_dataset(tmp_path, bundles):
    out = export_tasks(bundles, tmp_path / "hf")
    rows = [json.loads(line) for line in (out / "tasks.jsonl").read_text().splitlines()]
    assert len(rows) == len(bundles)
    assert all(r["canary"].startswith("OWB-CANARY-") for r in rows)
    assert (out / "files" / "vendor-shortlist" / "vendors" / "requirements.md").exists()
    card = (out / "README.md").read_text()
    assert card.startswith("---") and "license: cc-by-4.0" in card and "tasks.jsonl" in card


def test_site_embeds_data_safely(tmp_path, bundles):
    run_subject(load_subjects()["sim-budget"], bundles, tmp_path / "runs", repeats=1, index_version="v0.1")
    lb = build_leaderboard(load_rows([tmp_path / "runs"]), bundles, load_index_config("v0.1"))
    lb["subjects"][0]["label"] = "</script><b>x"
    p = tmp_path / "lb.json"
    p.write_text(json.dumps(lb))
    html = build_site(p, tmp_path / "site").read_text()
    assert "__OWB_DATA__" not in html and "</script><b>" not in html


def test_judge_panel_majority_and_family_exclusion(by_id):
    class J:
        def __init__(self, id, family, verdict):
            self.id, self.family, self.verdict = id, family, verdict

        def complete(self, system, user):
            return json.dumps({"verdict": self.verdict, "reason": "r"})

    b = by_id["vendor-shortlist"]
    w = World(b.world, b.workspace)
    for s in b.reference:
        w.call(s["tool"], s["args"])
    panel = JudgePanel([J("a", "acme", "no"), J("b", "beta", "yes"), J("c", "gamma", "yes")])
    rows = panel.grade(b, w.snapshot(), subject_family="acme")
    assert rows[0]["passed"] is True and [v["judge"] for v in rows[0]["votes"]] == ["b", "c"]
    assert parse_verdict('{"verdict": "no"}') is False and parse_verdict("garbage") is None
