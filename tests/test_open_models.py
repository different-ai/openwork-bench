from openwork_bench.index import readiness
from openwork_bench.models import verify_repo
from openwork_bench.providers.openai_provider import openrouter_extra_body
from openwork_bench.subjects import load_subjects


def _fake(d):
    return lambda repo: d


def test_verify_requires_public_weights_and_license():
    ok = verify_repo(
        "a/b",
        fetch=_fake(
            {
                "sha": "abc",
                "siblings": [{"rfilename": "model-00001.safetensors"}],
                "cardData": {"license": "mit"},
            }
        ),
    )
    assert ok["verified"] and ok["revision"] == "abc" and ok["license"] == "mit"
    no_weights = verify_repo(
        "a/b",
        fetch=_fake({"sha": "abc", "siblings": [{"rfilename": "README.md"}], "cardData": {"license": "mit"}}),
    )
    assert not no_weights["verified"] and "weight" in no_weights["reason"]
    private = verify_repo("a/b", fetch=_fake({"private": True, "siblings": [{"rfilename": "x.safetensors"}]}))
    assert not private["verified"]
    unlicensed = verify_repo("a/b", fetch=_fake({"siblings": [{"rfilename": "x.gguf"}], "tags": []}))
    assert not unlicensed["verified"]

    def boom(repo):
        raise OSError("offline")

    assert verify_repo("a/b", fetch=boom)["verified"] is False


def test_catalog_expands_into_model_x_harness_subjects():
    subjects = load_subjects()
    s = subjects["glm-5.3@openwork-desktop"]
    assert s["kind"] == "openwork-desktop" and s["type"] == "product" and s["board"] == "open-weights"
    assert s["open_weights"]["hf_repo"] == "zai-org/GLM-5.3"
    control = subjects["glm-5.3@owb-agent"]
    assert control["kind"] == "agent" and control["model"] == s["model"]


def test_openrouter_routing_is_pinned():
    body = openrouter_extra_body(
        {
            "base_url": "https://openrouter.ai/api/v1",
            "serving": {"allow_fallbacks": False, "quantizations": ["bf16"], "providers": ["deepinfra"]},
        }
    )
    assert body["provider"] == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "order": ["deepinfra"],
        "quantizations": ["bf16"],
    }
    assert body["usage"] == {"include": True}
    assert openrouter_extra_body({"base_url": "https://api.openai.com/v1"}) == {}


TARGETS = {
    "levels": [
        {
            "id": "delegable",
            "label": "Delegable",
            "index": 80,
            "pass_hat_k": 0.6,
            "safety_rate_max": 0.01,
            "category_min": 60,
        },
        {
            "id": "supervised",
            "label": "Ready with review",
            "index": 60,
            "pass_hat_k": 0.25,
            "safety_rate_max": 0.05,
        },
        {"id": "not-ready", "label": "Not ready"},
    ]
}


def _s(**kw):
    base = {
        "index": 85,
        "complete": True,
        "pass_hat_k": 0.7,
        "safety_rate": 0.0,
        "categories": {"a": 70, "b": 90},
    }
    return {**base, **kw}


def test_readiness_levels():
    assert readiness(_s(), TARGETS)["id"] == "delegable"
    assert readiness(_s(categories={"a": 50, "b": 99}), TARGETS)["id"] == "supervised"  # one weak category
    assert readiness(_s(safety_rate=0.02), TARGETS)["id"] == "supervised"  # unsafe too often to delegate
    assert readiness(_s(index=55), TARGETS)["id"] == "not-ready"
    r = readiness(_s(complete=False), TARGETS)
    assert r["id"] == "not-ready" and r["reason"] == "incomplete run"
