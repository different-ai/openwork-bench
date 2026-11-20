"""Subjects are what the benchmark scores: a model (or product) run through a harness.

Subject files live in subjects/*.yaml. Prices come from the subject file or pricing.yaml.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

SUBJECT_TYPES = {"model", "product", "reference", "simulated"}
SECRET_KEYS = {"api_key", "token", "secret"}


def repo_root() -> Path:
    env = os.environ.get("OWB_ROOT")
    if env:
        return Path(env)
    if (Path.cwd() / "subjects").is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parents[2]


def load_pricing(root: Path | None = None) -> dict[str, Any]:
    p = (root or repo_root()) / "pricing.yaml"
    if not p.exists():
        return {}
    return (yaml.safe_load(p.read_text()) or {}).get("models", {})


def load_subjects(root: Path | None = None) -> dict[str, dict[str, Any]]:
    root = root or repo_root()
    pricing = load_pricing(root)
    out: dict[str, dict[str, Any]] = {}
    for f in sorted((root / "subjects").glob("*.yaml")):
        s = yaml.safe_load(f.read_text()) or {}
        if not s.get("id"):
            continue
        s.setdefault("label", s["id"])
        s.setdefault("type", "model")
        if s["type"] not in SUBJECT_TYPES:
            raise ValueError(f"{f.name}: type must be one of {sorted(SUBJECT_TYPES)}")
        if (
            s.get("kind") in ("agent", "openwork-desktop")
            and "pricing" not in s
            and s.get("model") in pricing
        ):
            s["pricing"] = pricing[s["model"]]
        if s.get("kind") == "simulated":
            s["pricing"] = s.get("simulated", {}).get("pricing")
        s["_file"] = str(f.relative_to(root))
        out[s["id"]] = s
    from .models import expand_subjects

    for sid, s in expand_subjects(root).items():
        s["_file"] = "models/open-weights.yaml"
        out.setdefault(sid, s)
    return out


def is_verified_open(subject: dict[str, Any]) -> bool:
    return bool((subject.get("open_weights") or {}).get("verified"))


def public_config(subject: dict[str, Any]) -> dict[str, Any]:
    """The subject config as stored with results: no secrets, no private fields."""
    return {k: v for k, v in subject.items() if not k.startswith("_") and k not in SECRET_KEYS}


def config_hash(subject: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(public_config(subject), sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
