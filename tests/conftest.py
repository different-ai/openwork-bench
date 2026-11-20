from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("OWB_ROOT", str(ROOT))
os.environ.setdefault("OWB_TASKS_DIR", str(ROOT / "tasks"))


@pytest.fixture(scope="session")
def bundles():
    from openwork_bench.tasks import load_all

    return load_all(ROOT / "tasks")


@pytest.fixture(scope="session")
def by_id(bundles):
    return {b.id: b for b in bundles}
