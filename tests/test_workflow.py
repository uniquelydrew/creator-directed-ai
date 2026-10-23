from pathlib import Path

import pytest

from creator_ai.auth import create_authorization, create_key, load_private_key
from creator_ai.backends import SvgBackend
from creator_ai.core import CreativeSpecification, CreatorManifest, GenerationRequest
from creator_ai.registry import ModelRegistry
from creator_ai.workflow import CreatorWorkspace


def registry() -> ModelRegistry:
    return ModelRegistry.load(Path(__file__).parents[1] / "models" / "registry.json")


def identity_and_workspace(tmp_path):
    identity = create_key(tmp_path / "creator.pem", "passphrase")
    private = load_private_key(tmp_path / "creator.pem", "passphrase")
    return identity, private, CreatorWorkspace(tmp_path / "store")


@pytest.mark.parametrize(
    ("domain", "suffix", "constraints"),
    [("writing", ".txt", {}), ("visual", ".svg", {"palette": ["#111111", "#eeeeee"]}), ("music", ".mid", {"tempo": 120}), ("voice", ".wav", {})],
)
def test_signed_offline_workflow_exports_each_domain(tmp_path, domain, suffix, constraints):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization = create_authorization(identity, private, (domain,), ("generate", "approve", "export"))
    authorization_ref = workspace.store_authorization(authorization)
    specification = CreativeSpecification(domain, "demo", constraints)
    generation_ref, output = workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("a local demo", 42, specification), registry())
    generation = workspace._load_generation(generation_ref.digest)
    evaluation = workspace.evaluate(generation_ref.digest, True, "looks good")
    approval_ref = workspace.approve(generation_ref.digest, authorization_ref.digest, identity, private)
    exported = workspace.export(generation_ref.digest, authorization_ref.digest, approval_ref.digest, identity, tmp_path / f"output{suffix}")
    assert len(output.digest) == 64
    assert generation.policy_allowed
    assert workspace.store.read_json(evaluation.digest)["accepted"] is True
    assert exported.read_bytes() == workspace.store.read_bytes(generation.output_hash)


def test_generation_rejects_assets_not_named_by_authorization(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("writing",), ("generate",)))
    specification = CreativeSpecification("writing", "demo")
    with pytest.raises(PermissionError, match="assets"):
        workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification, asset_hashes=("unapproved",)), registry())


def test_stored_generation_prevents_record_substitution(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("writing",), ("generate", "approve", "export")))
    specification = CreativeSpecification("writing", "demo")
    generation_ref, _ = workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification), registry())
    approval_ref = workspace.approve(generation_ref.digest, authorization_ref.digest, identity, private)
    altered = workspace.store.put_json({**workspace.store.read_json(generation_ref.digest), "output_hash": "0" * 64})
    with pytest.raises(PermissionError, match="stored output"):
        workspace.export(altered.digest, authorization_ref.digest, approval_ref.digest, identity, tmp_path / "out.txt")


def test_other_creator_cannot_approve_generation(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    other = create_key(tmp_path / "other.pem", "passphrase")
    other_private = load_private_key(tmp_path / "other.pem", "passphrase")
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("writing",), ("generate", "approve", "export")))
    specification = CreativeSpecification("writing", "demo")
    generation_ref, _ = workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification), registry())
    with pytest.raises(PermissionError, match="generation creator"):
        workspace.approve(generation_ref.digest, authorization_ref.digest, other, other_private)


def test_verified_revocation_blocks_export_and_tampering_fails_closed(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("writing",), ("generate", "approve", "export")))
    specification = CreativeSpecification("writing", "demo")
    generation_ref, _ = workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification), registry())
    approval_ref = workspace.approve(generation_ref.digest, authorization_ref.digest, identity, private)
    workspace.revoke(authorization_ref.digest, identity, private)
    with pytest.raises(PermissionError, match="revoked"):
        workspace.export(generation_ref.digest, authorization_ref.digest, approval_ref.digest, identity, tmp_path / "out.txt")
    workspace._state_pointer(identity.creator_id).write_text('"not-a-real-digest"', encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        workspace.revoked_ids(identity)


def test_svg_escapes_prompt_and_rejects_unsafe_palette():
    manifest = CreatorManifest("creator", "Creator", "visual", "demo")
    result = SvgBackend().generate(manifest, GenerationRequest("<script>alert(1)</script>", specification=CreativeSpecification("visual", "demo")))
    assert "&lt;script&gt;" in result.content
    with pytest.raises(ValueError, match="palette"):
        SvgBackend().generate(manifest, GenerationRequest("prompt", specification=CreativeSpecification("visual", "demo", {"palette": ["#000000", '" onload="alert(1)']})))


def test_learned_music_is_denied_before_worker_or_provision_access(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("music",), ("generate",)))
    specification = CreativeSpecification("music", "demo")
    with pytest.raises(PermissionError, match="allowlist"):
        workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification), registry(),
                           model_id="facebook/musicgen-small", model_path=tmp_path, provision_hash="not-read", adapter_command=("not-run",))


def test_voice_cloning_requires_authorized_reference_asset(tmp_path):
    identity, private, workspace = identity_and_workspace(tmp_path)
    authorization_ref = workspace.store_authorization(create_authorization(identity, private, ("voice",), ("generate",)))
    specification = CreativeSpecification("voice", "demo")
    with pytest.raises(PermissionError, match="voice reference"):
        workspace.generate(identity, authorization_ref.digest, specification, GenerationRequest("prompt", specification=specification), registry(),
                           model_id="orionai/openvoice-v2", model_path=tmp_path, provision_hash="not-read", adapter_command=("not-run",))
