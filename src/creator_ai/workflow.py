"""Policy-gated creator workflow orchestration using immutable artifact digests."""
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
    RevocationState,
)
from .licensing import LicensePolicy
from .registry import ModelRegistry
from .store import ArtifactRef, ArtifactStore


class CreatorWorkspace:
    def __init__(self, root: str | Path):
        self.store = ArtifactStore(root)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _state_pointer(self, creator_id: str) -> Path:
        return self.root / f"revocation-state-{creator_id}.json"

    def _load_authorization(self, digest: str) -> AuthorizationRecord:
        try:
            return AuthorizationRecord(**self.store.read_json(digest))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid authorization artifact") from exc

    def _load_generation(self, digest: str) -> GenerationRecord:
        try:
            raw = self.store.read_json(digest)
            raw["policy_reasons"] = tuple(raw["policy_reasons"])
            raw["parent_hashes"] = tuple(raw["parent_hashes"])
            return GenerationRecord(**raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid generation artifact") from exc

    def _load_approval(self, digest: str) -> ApprovalRecord:
        try:
            return ApprovalRecord(**self.store.read_json(digest))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid approval artifact") from exc

    def register_creator(self, identity: CreatorIdentity) -> ArtifactRef:
        return self.store.put_json(identity.to_dict())

    def store_authorization(self, authorization: AuthorizationRecord) -> ArtifactRef:
        return self.store.put_json(authorization.to_dict())

    def register_asset(self, data: bytes, creator_id: str, license_id: str, filename: str = "") -> ArtifactRef:
        blob = self.store.put_bytes(data)
        return self.store.put_json({"creator_id": creator_id, "asset_hash": blob.digest, "license_id": license_id, "filename": filename, "version": "1"})

    def register_dataset(self, dataset_id: str, asset_hashes: tuple[str, ...]) -> ArtifactRef:
        if not asset_hashes:
            raise ValueError("dataset must contain at least one asset")
        return self.store.put_json({"dataset_id": dataset_id, "asset_hashes": list(asset_hashes), "version": "1"})

    def _load_revocation_state(self, identity: CreatorIdentity) -> tuple[set[str], str | None, int]:
        pointer = self._state_pointer(identity.creator_id)
        if not pointer.exists():
            return set(), None, 0
        digest = json.loads(pointer.read_text(encoding="utf-8"))
        if not isinstance(digest, str):
            raise TypeError("invalid revocation-state pointer")
        revocations: set[str] = set()
        expected_sequence: int | None = None
        visited: set[str] = set()
        current: str | None = digest
        while current:
            if current in visited:
                raise ValueError("revocation-state chain contains a loop")
            visited.add(current)
            try:
                raw = self.store.read_json(current)
                raw["revocation_hashes"] = tuple(raw["revocation_hashes"])
                state = RevocationState(**raw)
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("invalid revocation-state artifact") from exc
            if state.creator_id != identity.creator_id or not verify(identity.public_key, state.unsigned_dict(), state.signature):
                raise PermissionError("invalid signed revocation state")
            if expected_sequence is not None and state.sequence != expected_sequence - 1:
                raise ValueError("revocation-state sequence is not contiguous")
            expected_sequence = state.sequence
            for revocation_hash in state.revocation_hashes:
                try:
                    record = RevocationRecord(**self.store.read_json(revocation_hash))
                except (TypeError, ValueError) as exc:
                    raise ValueError("invalid revocation artifact") from exc
                if record.creator_id != identity.creator_id or not verify(identity.public_key, record.unsigned_dict(), record.signature):
                    raise PermissionError("invalid signed revocation")
                revocations.add(record.authorization_id)
            current = state.previous_hash
        return revocations, digest, expected_sequence or 0

    def revoked_ids(self, identity: CreatorIdentity) -> set[str]:
        return self._load_revocation_state(identity)[0]

    def revoke(self, authorization_hash: str, identity: CreatorIdentity, private: Ed25519PrivateKey) -> ArtifactRef:
        authorization = self._load_authorization(authorization_hash)
        authorization_allowed(authorization, identity, authorization.domains[0], "generate", revoked=self.revoked_ids(identity))
        record = revoke_authorization(identity, private, authorization.authorization_id)
        revocation_ref = self.store.put_json(record.to_dict())
        _, previous_hash, previous_sequence = self._load_revocation_state(identity)
        unsigned = {"creator_id": identity.creator_id, "sequence": previous_sequence + 1, "revocation_hashes": [revocation_ref.digest], "previous_hash": previous_hash, "version": "1"}
        state = RevocationState(identity.creator_id, previous_sequence + 1, (revocation_ref.digest,), previous_hash, sign(private, unsigned))
        state_ref = self.store.put_json(state.to_dict())
        self._state_pointer(identity.creator_id).write_text(json.dumps(state_ref.digest), encoding="utf-8")
        return revocation_ref

    def generate(self, identity: CreatorIdentity, authorization_hash: str, specification: CreativeSpecification, request: GenerationRequest, registry: ModelRegistry) -> tuple[ArtifactRef, ArtifactRef]:
        authorization = self._load_authorization(authorization_hash)
        authorization_allowed(authorization, identity, specification.domain, "generate", request.asset_hashes, self.revoked_ids(identity))
        backend = deterministic_backend(specification.domain)
        model = registry.get(backend.model_id)
        decision = LicensePolicy().evaluate(model, domain=specification.domain, consent_verified=True)
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
        manifest = CreatorManifest(identity.creator_id, identity.display_name, specification.domain, "creator-authorized")
        result = backend.generate(manifest, request)
        output = self.store.put_bytes(result.binary if result.binary is not None else result.content.encode(), result.media_type)
        request_ref = self.store.put_json(request.to_dict())
        spec_ref = self.store.put_json(specification.to_dict())
        record = GenerationRecord(str(uuid4()), identity.creator_id, authorization.authorization_id, authorization_hash, specification.domain, result.backend, result.model_id, request_ref.digest, spec_ref.digest, output.digest, True, decision.reasons, request.seed, tuple(request.asset_hashes))
        return self.store.put_json(record.to_dict()), output

    def evaluate(self, generation_hash: str, accepted: bool, notes: str = "") -> ArtifactRef:
        generation = self._load_generation(generation_hash)
        return self.store.put_json(EvaluationResult(generation.record_id, accepted, notes).to_dict())

    def approve(self, generation_hash: str, authorization_hash: str, identity: CreatorIdentity, private: Ed25519PrivateKey, accepted: bool = True) -> ArtifactRef:
        generation = self._load_generation(generation_hash)
        authorization = self._load_authorization(authorization_hash)
        if generation.creator_id != identity.creator_id or generation.authorization_hash != authorization_hash:
            raise PermissionError("approval must use the stored generation creator and authorization")
        authorization_allowed(authorization, identity, generation.domain, "approve", revoked=self.revoked_ids(identity))
        approval_id = str(uuid4())
        unsigned = {"approval_id": approval_id, "generation_id": generation.record_id, "generation_hash": generation_hash, "output_hash": generation.output_hash, "creator_id": identity.creator_id, "accepted": accepted, "version": "1"}
        return self.store.put_json(ApprovalRecord(approval_id, generation.record_id, generation_hash, generation.output_hash, identity.creator_id, accepted, sign(private, unsigned)).to_dict())

    def export(self, generation_hash: str, authorization_hash: str, approval_hash: str, identity: CreatorIdentity, destination: str | Path) -> Path:
        generation = self._load_generation(generation_hash)
        authorization = self._load_authorization(authorization_hash)
        approval = self._load_approval(approval_hash)
        payload = asdict(approval); signature = payload.pop("signature")
        if generation.creator_id != identity.creator_id or generation.authorization_hash != authorization_hash:
            raise PermissionError("export must use the stored generation creator and authorization")
        authorization_allowed(authorization, identity, generation.domain, "export", revoked=self.revoked_ids(identity))
        if not approval.accepted or approval.creator_id != generation.creator_id or approval.generation_id != generation.record_id or approval.generation_hash != generation_hash or approval.output_hash != generation.output_hash or not verify(identity.public_key, payload, signature):
            raise PermissionError("a valid approval bound to the stored output is required for export")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.store.read_bytes(generation.output_hash))
        return target
