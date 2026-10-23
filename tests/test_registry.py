import json

import pytest

from creator_ai.licensing import LicensePolicy
from creator_ai.registry import ModelRecord, ModelRegistry, RegistryError

MODEL = {
    "model_id": "example/model", "revision": "a" * 40, "license_id": "Apache-2.0",
    "domains": ["writing"], "source_url": "https://example.org/model",
    "license_url": "https://example.org/license",
}


def test_registry_roundtrip(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema_version": 1, "models": [MODEL]}))
    registry = ModelRegistry.load(path)
    assert registry.get("example/model").revision == "a" * 40
    assert len(registry.list()) == 1


@pytest.mark.parametrize("field,value", [
    ("revision", "main"), ("license_id", ""), ("domains", []),
    ("domains", ["unknown"]), ("source_url", "http://example.org"),
    ("requires_consent", "yes"),
])
def test_invalid_metadata_rejected(field, value):
    with pytest.raises(RegistryError):
        ModelRecord.from_dict({**MODEL, field: value})


def test_unknown_and_duplicate_rejected(tmp_path):
    with pytest.raises(RegistryError):
        ModelRecord.from_dict({**MODEL, "unexpected": 1})
    with pytest.raises(RegistryError):
        ModelRegistry((ModelRecord.from_dict(MODEL), ModelRecord.from_dict(MODEL)))


def test_policy_denies_unapproved_license():
    model = ModelRecord.from_dict({**MODEL, "license_id": "LicenseRef-Unknown"})
    decision = LicensePolicy().evaluate(model, domain="writing")
    assert not decision.allowed
    assert "allowlist" in decision.reasons[0]


def test_policy_checks_domain_and_consent():
    model = ModelRecord.from_dict({**MODEL, "requires_consent": True})
    policy = LicensePolicy()
    assert not policy.evaluate(model, domain="voice").allowed
    assert not policy.evaluate(model, domain="writing").allowed
    assert policy.evaluate(model, domain="writing", consent_verified=True).allowed
    with pytest.raises(PermissionError):
        policy.require_allowed(model, domain="writing")
