import json

from openwork_bench.index import build_leaderboard, load_index_config
from openwork_bench.runner import load_rows, regrade, run_subject
from openwork_bench.subjects import load_subjects


def _run(tmp_path, bundles, ids, repeats=2):
    subjects = load_subjects()
    cfg = load_index_config("v0.1")
    for sid in ids:
        run_subject(
            subjects[sid], bundles, tmp_path, repeats=repeats, workers=4, index_version=cfg["version"]
        )
    return cfg, load_rows([tmp_path])


def test_end_to_end_leaderboard(tmp_path, bundles):
    cfg, rows = _run(tmp_path, bundles, ["reference-oracle", "reference-noop", "sim-balanced"])
    lb = build_leaderboard(rows, bundles, cfg)
    by = {s["id"]: s for s in lb["subjects"]}
    assert by["reference-oracle"]["index"] == 100.0
    assert by["reference-noop"]["index"] < 5
    sim = by["sim-balanced"]
    assert 0 < sim["index"] < 100 and sim["ci"][0] <= sim["index"] <= sim["ci"][1]
    assert sim["cost_per_task"] > 0 and sim["complete"]
    assert lb["subjects"][0]["id"] == "reference-oracle"


def test_stale_and_voided_rows_are_excluded(tmp_path, bundles):
    cfg, rows = _run(tmp_path, bundles, ["sim-budget"], repeats=1)
    rows[0]["task_version"] = 0  # pretend the task was fixed after this run
    lb = build_leaderboard(rows, bundles, cfg)
    assert lb["subjects"][0]["excluded"]["stale"] == 1
    errata = [{"id": "E-1", "action": "void", "affects": {"runs": [rows[1]["run_id"]]}}]
    lb = build_leaderboard(rows, bundles, cfg, errata=errata)
    assert lb["subjects"] == [] and lb["errata_applied"] == ["E-1"]


def test_runs_are_reproducible_and_regradable(tmp_path, bundles):
    subjects = load_subjects()
    a = run_subject(subjects["sim-frontier"], bundles, tmp_path / "a", repeats=1, index_version="v0.1")
    b = run_subject(subjects["sim-frontier"], bundles, tmp_path / "b", repeats=1, index_version="v0.1")
    scores = lambda d: [r["score"] for r in load_rows([d])]  # noqa: E731
    assert scores(a) == scores(b)
    assert regrade(a, {x.id: x for x in bundles}) == 0
    manifest = json.loads((a / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["suite_fingerprint"]
    assert (a / "trajectories").is_dir()
