
import pytest

from creator_ai.auth import authorization_allowed, create_authorization, create_key, load_private_key
from creator_ai.backends import SvgBackend
from creator_ai.core import CreativeSpecification, CreatorManifest, GenerationRequest
from creator_ai.workflow import CreatorWorkspace


@pytest.mark.parametrize(
    ("domain", "suffix", "constraints"),
    [
        ("writing", ".txt", {}),
        ("visual", ".svg", {"palette": ["#111111", "#eeeeee"]}),
        ("music", ".mid", {"tempo": 120}),
        ("voice", ".wav", {}),
    ],
)
def test_signed_offline_workflow_exports_each_domain(tmp_path, domain, suffix, constraints):
    key_path = tmp_path / "creator.pem"
    identity = create_key(key_path, "passphrase")
    private = load_private_key(key_path, "passphrase")
    workspace = CreatorWorkspace(tmp_path / "store")
    authorization = create_authorization(identity, private, (domain,), ("generate", "export", "approve"))
    specification = CreativeSpecification(domain, "demo", constraints)
    record, output = workspace.generate(identity, authorization, specification, GenerationRequest("a local demo", 42, specification))
    assert len(output.digest) == 64
    assert record.policy_allowed
    evaluation = workspace.evaluate(record, True, "looks good")
    assert workspace.store.read_json(evaluation.digest)["accepted"] is True
    approval = workspace.approve(record, authorization, identity, private)
    exported = workspace.export(record, authorization, approval, identity, tmp_path / f"output{suffix}")
    assert exported.read_bytes() == workspace.store.read_bytes(record.output_hash)


def test_authorization_is_required_and_revocable(tmp_path):
    key_path = tmp_path / "creator.pem"
    identity = create_key(key_path, "passphrase")
    private = load_private_key(key_path, "passphrase")
    authorization = create_authorization(identity, private, ("voice",), ("generate",))
    with pytest.raises(PermissionError, match="does not permit"):
        authorization_allowed(authorization, identity, "writing", "generate")
    with pytest.raises(PermissionError, match="revoked"):
        authorization_allowed(authorization, identity, "voice", "generate", revoked={authorization.authorization_id})


def test_signed_revocation_is_stored(tmp_path):
    identity = create_key(tmp_path / "creator.pem", "passphrase")
    private = load_private_key(tmp_path / "creator.pem", "passphrase")
    authorization = create_authorization(identity, private, ("writing",), ("generate",))
    workspace = CreatorWorkspace(tmp_path / "store")
    revocation = workspace.revoke(authorization, identity, private)
    assert workspace.store.put_json(revocation.to_dict()).digest
    assert authorization.authorization_id in CreatorWorkspace(tmp_path / "store").revoked_ids(identity)


def test_artifact_store_rejects_tampering(tmp_path):
    workspace = CreatorWorkspace(tmp_path / "store")
    artifact = workspace.store.put_bytes(b"original")
    artifact.path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        workspace.store.read_bytes(artifact.digest)


def test_generation_rejects_assets_not_named_by_authorization(tmp_path):
    identity = create_key(tmp_path / "creator.pem", "passphrase")
    private = load_private_key(tmp_path / "creator.pem", "passphrase")
    workspace = CreatorWorkspace(tmp_path / "store")
    authorization = create_authorization(identity, private, ("writing",), ("generate",))
    specification = CreativeSpecification("writing", "demo")
    with pytest.raises(PermissionError, match="assets"):
        workspace.generate(identity, authorization, specification, GenerationRequest("prompt", specification=specification, asset_hashes=("unapproved",)))


def test_other_creator_cannot_approve_or_export_generation(tmp_path):
    identity = create_key(tmp_path / "creator.pem", "passphrase")
    private = load_private_key(tmp_path / "creator.pem", "passphrase")
    other = create_key(tmp_path / "other.pem", "passphrase")
    other_private = load_private_key(tmp_path / "other.pem", "passphrase")
    workspace = CreatorWorkspace(tmp_path / "store")
    authorization = create_authorization(identity, private, ("writing",), ("generate", "approve", "export"))
    specification = CreativeSpecification("writing", "demo")
    record, _ = workspace.generate(identity, authorization, specification, GenerationRequest("prompt", specification=specification))
    with pytest.raises(PermissionError, match="generation creator"):
        workspace.approve(record, authorization, other, other_private)


def test_revocation_blocks_certified_export(tmp_path):
    identity = create_key(tmp_path / "creator.pem", "passphrase")
    private = load_private_key(tmp_path / "creator.pem", "passphrase")
    workspace = CreatorWorkspace(tmp_path / "store")
    authorization = create_authorization(identity, private, ("writing",), ("generate", "approve", "export"))
    specification = CreativeSpecification("writing", "demo")
    record, _ = workspace.generate(identity, authorization, specification, GenerationRequest("prompt", specification=specification))
    approval = workspace.approve(record, authorization, identity, private)
    workspace.revoke(authorization, identity, private)
    with pytest.raises(PermissionError, match="revoked"):
        workspace.export(record, authorization, approval, identity, tmp_path / "out.txt")


def test_svg_escapes_prompt_and_rejects_unsafe_palette():
    manifest = CreatorManifest("creator", "Creator", "visual", "demo")
    result = SvgBackend().generate(manifest, GenerationRequest("<script>alert(1)</script>", specification=CreativeSpecification("visual", "demo")))
    assert "&lt;script&gt;" in result.content
    with pytest.raises(ValueError, match="palette"):
        SvgBackend().generate(manifest, GenerationRequest("prompt", specification=CreativeSpecification("visual", "demo", {"palette": ["#000000", '" onload="alert(1)']})))
