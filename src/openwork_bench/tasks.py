"""Load task folders into TaskBundles."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .schema import Task

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".tsv"}


@dataclass
class TaskBundle:
    task: Task
    world: dict[str, Any]
    workspace: dict[str, str]
    reference: list[dict[str, Any]]
    path: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.task.id

    def fingerprint(self) -> str:
        """Content hash of everything that defines the task. Changes when anything changes."""
        payload = json.dumps(
            {
                "task": self.task.model_dump(mode="json"),
                "world": self.world,
                "workspace": self.workspace,
                "reference": self.reference,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def default_tasks_dir() -> Path:
    env = os.environ.get("OWB_TASKS_DIR")
    if env:
        return Path(env)
    here = Path.cwd() / "tasks"
    if here.is_dir():
        return here
    # Fall back to the repository checkout this package lives in.
    return Path(__file__).resolve().parents[2] / "tasks"


def deep_merge(base: Any, override: Any) -> Any:
    """Merge override into base. Dicts merge; lists of dicts with ids merge by id; other lists append."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = deep_merge(base[k], v) if k in base else v
        return out
    if isinstance(base, list) and isinstance(override, list):
        if all(isinstance(x, dict) and "id" in x for x in base + override):
            merged = {x["id"]: x for x in base}
            for x in override:
                merged[x["id"]] = deep_merge(merged[x["id"]], x) if x["id"] in merged else x
            return list(merged.values())
        return base + override
    return override


def _load_yaml(path: Path) -> Any:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def load_world(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    parent = data.pop("extends", None)
    if parent:
        base = load_world((path.parent / parent).resolve())
        data = deep_merge(base, data)
    return data


def load_task(folder: Path) -> TaskBundle:
    folder = Path(folder)
    task = Task.model_validate(_load_yaml(folder / "task.yaml"))
    world = load_world(folder / "world.yaml") if (folder / "world.yaml").exists() else {}
    reference = (
        _load_yaml(folder / "reference.yaml").get("steps", []) if (folder / "reference.yaml").exists() else []
    )
    workspace: dict[str, str] = {}
    ws = folder / "workspace"
    if ws.is_dir():
        for p in sorted(ws.rglob("*")):
            if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
                workspace["/" + p.relative_to(ws).as_posix()] = p.read_text()
    return TaskBundle(task=task, world=world, workspace=workspace, reference=reference, path=folder)


def discover(tasks_dir: Path | None = None) -> list[Path]:
    root = Path(tasks_dir or default_tasks_dir())
    return sorted(p.parent for p in root.rglob("task.yaml") if "_shared" not in p.parts)


def load_all(tasks_dir: Path | None = None, splits: list[str] | None = None) -> list[TaskBundle]:
    bundles = [load_task(p) for p in discover(tasks_dir)]
    if splits:
        bundles = [b for b in bundles if b.task.split in splits]
    return bundles


def select(bundles: list[TaskBundle], selector: str | None) -> list[TaskBundle]:
    """Select tasks by 'all', a category name, a comma list of ids, or an id prefix."""
    if not selector or selector == "all":
        return bundles
    wanted = [s.strip() for s in selector.split(",") if s.strip()]
    out = []
    for b in bundles:
        if any(w == b.id or w == b.task.category or b.id.startswith(w) for w in wanted):
            out.append(b)
    return out


def suite_fingerprint(bundles: list[TaskBundle]) -> str:
    h = hashlib.sha256()
    for b in sorted(bundles, key=lambda b: b.id):
        h.update(f"{b.id}@{b.task.version}:{b.fingerprint()}".encode())
    return h.hexdigest()[:16]
