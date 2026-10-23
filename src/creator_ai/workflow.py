"""Policy-gated creator workflow orchestration and provenance."""
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .auth import authorization_allowed, revoke_authorization, sign, verify
from .backends import deterministic_backend
from .core import (
    ApprovalRecord,
    AuthorizationRecord,
    CreativeSpecification,
    CreatorIdentity,
    CreatorManifest,
    EvaluationResult,
    GenerationRecord,
    GenerationRequest,
    RevocationRecord,
)
from .licensing import LicensePolicy
from .registry import ModelRecord
from .store import ArtifactRef, ArtifactStore


class CreatorWorkspace:
    def __init__(self, root: str | Path):
        self.store = ArtifactStore(root)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def _revocation_index(self) -> Path:
        return self.root / "revoked-authorizations.json"

    def revoked_ids(self, identity: CreatorIdentity) -> set[str]:
        if not self._revocation_index.exists():
            return set()
        data = json.loads(self._revocation_index.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("invalid local revocation index")
        revoked: set[str] = set()
        for digest in data:
            raw = self.store.read_json(digest)
            try:
                record = RevocationRecord(**raw)
            except TypeError as exc:
                raise ValueError("invalid revocation record") from exc
            if record.creator_id != identity.creator_id or not verify(identity.public_key, record.unsigned_dict(), record.signature):
                raise PermissionError("invalid revocation record")
            revoked.add(record.authorization_id)
        return revoked

    def register_creator(self, identity: CreatorIdentity) -> ArtifactRef:
        return self.store.put_json(identity.to_dict())

    def register_asset(self, data: bytes, creator_id: str, license_id: str, filename: str = "") -> ArtifactRef:
        blob = self.store.put_bytes(data)
        return self.store.put_json({"creator_id": creator_id, "asset_hash": blob.digest, "license_id": license_id, "filename": filename, "version": "1"})

    def register_dataset(self, dataset_id: str, asset_hashes: tuple[str, ...]) -> ArtifactRef:
        if not asset_hashes:
            raise ValueError("dataset must contain at least one asset")
        return self.store.put_json({"dataset_id": dataset_id, "asset_hashes": list(asset_hashes), "version": "1"})

    def revoke(self, authorization: AuthorizationRecord, identity: CreatorIdentity, private: Ed25519PrivateKey) -> RevocationRecord:
        record = revoke_authorization(identity, private, authorization.authorization_id)
        artifact = self.store.put_json(record.to_dict())
        self._revocation_index.write_text(json.dumps(sorted(self._revocation_digests() | {artifact.digest})), encoding="utf-8")
        return record

    def _revocation_digests(self) -> set[str]:
        if not self._revocation_index.exists():
            return set()
        data = json.loads(self._revocation_index.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("invalid local revocation index")
        return set(data)

    def generate(self, identity: CreatorIdentity, authorization: AuthorizationRecord, specification: CreativeSpecification, request: GenerationRequest) -> tuple[GenerationRecord, ArtifactRef]:
        authorization_allowed(authorization, identity, specification.domain, "generate", request.asset_hashes, self.revoked_ids(identity))
        backend = deterministic_backend(specification.domain)
        model = ModelRecord("local/deterministic", "0" * 40, "Apache-2.0", tuple(backend.capabilities()["domains"]), "https://example.invalid/local", "https://www.apache.org/licenses/LICENSE-2.0")
        decision = LicensePolicy().evaluate(model, domain=specification.domain, consent_verified=True)
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
        manifest = CreatorManifest(identity.creator_id, identity.display_name, specification.domain, "creator-authorized")
        result = backend.generate(manifest, request)
        output = self.store.put_bytes(result.binary if result.binary is not None else result.content.encode(), result.media_type)
        request_ref = self.store.put_json(request.to_dict())
        spec_ref = self.store.put_json(specification.to_dict())
        record = GenerationRecord(str(uuid4()), identity.creator_id, authorization.authorization_id, specification.domain, result.backend, result.model_id, request_ref.digest, spec_ref.digest, output.digest, True, decision.reasons, request.seed, tuple(request.asset_hashes))
        self.store.put_json(authorization.to_dict())
        self.store.put_json(record.to_dict())
        return record, output

    def evaluate(self, generation: GenerationRecord, accepted: bool, notes: str = "") -> ArtifactRef:
        return self.store.put_json(EvaluationResult(generation.record_id, accepted, notes).to_dict())

    def approve(self, generation: GenerationRecord, authorization: AuthorizationRecord, identity: CreatorIdentity, private: Ed25519PrivateKey, accepted: bool = True) -> ApprovalRecord:
        if generation.creator_id != identity.creator_id or generation.authorization_id != authorization.authorization_id:
            raise PermissionError("approval must use the generation creator and authorization")
        authorization_allowed(authorization, identity, generation.domain, "approve", revoked=self.revoked_ids(identity))
        approval_id = str(uuid4())
        unsigned = {"approval_id": approval_id, "generation_id": generation.record_id, "creator_id": identity.creator_id, "accepted": accepted, "version": "1"}
        approval = ApprovalRecord(approval_id, generation.record_id, identity.creator_id, accepted, sign(private, unsigned))
        self.store.put_json(approval.to_dict())
        return approval

    def export(self, generation: GenerationRecord, authorization: AuthorizationRecord, approval: ApprovalRecord, identity: CreatorIdentity, destination: str | Path) -> Path:
        payload = asdict(approval); signature = payload.pop("signature")
        if generation.creator_id != identity.creator_id or generation.authorization_id != authorization.authorization_id:
            raise PermissionError("export must use the generation creator and authorization")
        authorization_allowed(authorization, identity, generation.domain, "export", revoked=self.revoked_ids(identity))
        if not approval.accepted or approval.creator_id != generation.creator_id or approval.generation_id != generation.record_id or not verify(identity.public_key, payload, signature):
            raise PermissionError("a valid accepted approval is required for export")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.store.read_bytes(generation.output_hash))
        return target
