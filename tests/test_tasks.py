from openwork_bench.schema import CATEGORIES
from openwork_bench.validate import validate_all


def test_every_task_is_solvable_and_not_gameable(bundles):
    report = validate_all(bundles)
    assert report, "no tasks found"
    assert {k: v for k, v in report.items() if v} == {}


def test_sample_suite_covers_every_category(bundles):
    assert {b.task.category for b in bundles} == set(CATEGORIES)


def test_canaries_are_unique(bundles):
    canaries = [b.task.canary for b in bundles]
    assert len(canaries) == len(set(canaries))


def test_fingerprint_changes_with_content(by_id):
    b = by_id["vendor-shortlist"]
    before = b.fingerprint()
    b.workspace["/vendors/requirements.md"] += "\n"
    try:
        assert b.fingerprint() != before
    finally:
        b.workspace["/vendors/requirements.md"] = b.workspace["/vendors/requirements.md"][:-1]
