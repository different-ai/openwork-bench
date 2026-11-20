"""The open-weight model catalog: load, verify against Hugging Face, and expand into subjects.

A result only counts on the open-weight board when the model's weights are verified: the
Hugging Face repo is public, contains weight files, and has a license, pinned to an exact
revision in models/open-weights.lock.json.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt")


def catalog_path(root: Path) -> Path:
    return root / "models" / "open-weights.yaml"


def lock_path(root: Path) -> Path:
    return root / "models" / "open-weights.lock.json"


def load_catalog(root: Path) -> dict[str, Any]:
    p = catalog_path(root)
    if not p.exists():
        return {"models": [], "harnesses": [], "defaults": {}}
    return yaml.safe_load(p.read_text()) or {}


def load_lock(root: Path) -> dict[str, Any]:
    p = lock_path(root)
    return json.loads(p.read_text()) if p.exists() else {}


def _hf_get(repo: str, timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(
        f"https://huggingface.co/api/models/{repo}", headers={"User-Agent": "openwork-bench"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def verify_repo(repo: str, fetch=_hf_get) -> dict[str, Any]:
    """Check that a Hugging Face repo publishes open weights. Never raises."""
    out: dict[str, Any] = {"hf_repo": repo, "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        d = fetch(repo)
    except urllib.error.HTTPError as e:
        return {**out, "verified": False, "reason": f"HTTP {e.code} from Hugging Face"}
    except Exception as e:  # network, JSON
        return {**out, "verified": False, "reason": f"lookup failed: {e}"}
    files = [s.get("rfilename", "") for s in d.get("siblings", [])]
    weights = [f for f in files if f.endswith(WEIGHT_SUFFIXES)]
    card = d.get("cardData") or {}
    license_ = card.get("license") or next(
        (t.split(":", 1)[1] for t in d.get("tags", []) if t.startswith("license:")), None
    )
    out.update(
        revision=d.get("sha"),
        license=license_,
        license_name=card.get("license_name"),
        gated=d.get("gated"),
        weight_files=len(weights),
        last_modified=d.get("lastModified"),
    )
    if d.get("private"):
        return {**out, "verified": False, "reason": "repository is private"}
    if not weights:
        return {**out, "verified": False, "reason": "no weight files published"}
    if not license_:
        return {**out, "verified": False, "reason": "no license declared"}
    return {**out, "verified": True, "reason": "public weights with a declared license"}


def verify_catalog(root: Path, fetch=_hf_get) -> dict[str, Any]:
    cat = load_catalog(root)
    lock = {m["key"]: verify_repo(m["hf_repo"], fetch=fetch) for m in cat.get("models", [])}
    lock_path(root).write_text(json.dumps(lock, indent=2) + "\n")
    return lock


def expand_subjects(root: Path) -> dict[str, dict[str, Any]]:
    """Turn each catalog model into one subject per harness: '<key>@<harness>'."""
    cat = load_catalog(root)
    lock = load_lock(root)
    defaults = cat.get("defaults", {})
    out: dict[str, dict[str, Any]] = {}
    for m in cat.get("models", []):
        weights = {
            "hf_repo": m["hf_repo"],
            **{k: v for k, v in lock.get(m["key"], {}).items() if k != "hf_repo"},
        }
        for harness in cat.get("harnesses", ["owb-agent"]):
            sid = f"{m['key']}@{harness}"
            s = {
                **{k: v for k, v in defaults.items() if k != "serving"},
                "id": sid,
                "label": m["label"] if harness == "openwork-desktop" else f"{m['label']} · plain loop",
                "type": "product" if harness == "openwork-desktop" else "model",
                "kind": "openwork-desktop" if harness == "openwork-desktop" else "agent",
                "harness": harness,
                "model": m["route"],
                "model_key": m["key"],
                "family": m.get("family"),
                "tier": m.get("tier"),
                "board": "open-weights",
                "open_weights": weights,
                "serving": {**defaults.get("serving", {}), **m.get("serving", {})},
                "pricing": m.get("pricing"),
            }
            out[sid] = s
    return out
