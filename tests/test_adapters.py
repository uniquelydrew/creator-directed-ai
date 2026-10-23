import sys
from pathlib import Path

import pytest

from creator_ai.adapters import AdapterError, ModelProvision, ProcessAdapter, import_model, verify_model
from creator_ai.core import CreativeSpecification, GenerationRequest
from creator_ai.registry import ModelRegistry
from creator_ai.store import ArtifactStore


def registry() -> ModelRegistry:
    return ModelRegistry.load(Path(__file__).parents[1] / "models" / "registry.json")


def test_imported_model_manifest_detects_tampering(tmp_path):
    source = tmp_path / "model"
    source.mkdir()
    (source / "weights.bin").write_bytes(b"known-weight")
    store = ArtifactStore(tmp_path / "store")
    model = registry().get("black-forest-labs/FLUX.1-schnell")
    ref = import_model(store, model, source)
    provision = ModelProvision(**store.read_json(ref.digest))
    verify_model(model, provision, source)
    (source / "weights.bin").write_bytes(b"altered-weight")
    with pytest.raises(AdapterError, match="do not match"):
        verify_model(model, provision, source)


def test_process_adapter_rejects_escaped_output(tmp_path):
    model = registry().get("black-forest-labs/FLUX.1-schnell")
    source = tmp_path / "model"
    source.mkdir()
    code = "import json,sys; json.load(sys.stdin); print(json.dumps({'output_filename':'../escape.png','media_type':'image/png'}))"
    adapter = ProcessAdapter((sys.executable, "-c", code))
    with pytest.raises(AdapterError, match="output"):
        adapter.generate(model, source, CreativeSpecification("visual", "test"), GenerationRequest("test"), ())


def test_process_adapter_accepts_direct_output(tmp_path):
    model = registry().get("black-forest-labs/FLUX.1-schnell")
    source = tmp_path / "model"
    source.mkdir()
    code = ("import json,sys,pathlib; r=json.load(sys.stdin); "
            "pathlib.Path(r['output_dir'],'result.png').write_bytes(b'png'); "
            "print(json.dumps({'output_filename':'result.png','media_type':'image/png','metadata':{'seed':7}}))")
    result = ProcessAdapter((sys.executable, "-c", code)).generate(
        model, source, CreativeSpecification("visual", "test"), GenerationRequest("test", 7), ())
    assert result.binary == b"png"
    assert result.metadata["seed"] == 7


def test_musicgen_is_denied_by_default_policy():
    from creator_ai.licensing import LicensePolicy

    decision = LicensePolicy().evaluate(registry().get("facebook/musicgen-small"), domain="music")
    assert not decision.allowed
    assert "allowlist" in decision.reasons[0]
