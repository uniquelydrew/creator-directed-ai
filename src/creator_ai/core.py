"""Versioned, JSON-serializable records shared by creator workflows."""
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

DOMAINS = frozenset({"visual", "writing", "music", "voice"})


def _require(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty")


@dataclass(frozen=True)
class CreatorIdentity:
    creator_id: str
    display_name: str
    public_key: str
    version: str = "1"

    def validate(self) -> None:
        _require(self.creator_id, "creator_id")
        _require(self.display_name, "display_name")
        _require(self.public_key, "public_key")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class AssetRecord:
    creator_id: str
    asset_hash: str
    license_id: str
    filename: str = ""
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        _require(self.creator_id, "creator_id")
        _require(self.asset_hash, "asset_hash")
        _require(self.license_id, "license_id")
        return asdict(self)


@dataclass(frozen=True)
class DatasetSnapshot:
    dataset_id: str
    asset_hashes: tuple[str, ...]
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        _require(self.dataset_id, "dataset_id")
        if not self.asset_hashes:
            raise ValueError("dataset must contain at least one asset")
        return {**asdict(self), "asset_hashes": list(self.asset_hashes)}


@dataclass(frozen=True)
class CreativeSpecification:
    domain: str
    title: str
    constraints: dict[str, Any] = field(default_factory=dict)
    canon: tuple[str, ...] = ()
    version: str = "1"

    def validate(self) -> None:
        if self.domain not in DOMAINS:
            raise ValueError("Unsupported domain")
        _require(self.title, "title")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {**asdict(self), "canon": list(self.canon)}


@dataclass(frozen=True)
class GenerationRequest:
    """A request that remains compatible with the original prompt/seed API."""

    prompt: str
    seed: int = 0
    specification: CreativeSpecification | None = None
    asset_hashes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        _require(self.prompt, "prompt")
        return {"prompt": self.prompt, "seed": self.seed,
                "specification": self.specification.to_dict() if self.specification else None,
                "asset_hashes": list(self.asset_hashes)}


@dataclass(frozen=True)
class GenerationResult:
    """Backward-compatible in-memory result returned by a backend."""

    content: str
    backend: str
    model_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    binary: bytes | None = None
    media_type: str = "text/plain"


@dataclass(frozen=True)
class GenerationRecord:
    record_id: str
    creator_id: str
    authorization_id: str
    authorization_hash: str
    domain: str
    backend: str
    model_id: str
    request_hash: str
    specification_hash: str | None
    output_hash: str
    policy_allowed: bool
    policy_reasons: tuple[str, ...]
    seed: int
    parent_hashes: tuple[str, ...] = ()
    model_manifest_hash: str = ""
    runtime_version: str = ""
    worker_metadata: dict[str, Any] = field(default_factory=dict)
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "policy_reasons": list(self.policy_reasons), "parent_hashes": list(self.parent_hashes)}


@dataclass(frozen=True)
class EvaluationResult:
    generation_id: str
    accepted: bool
    notes: str = ""
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalRecord:
    approval_id: str
    generation_id: str
    generation_hash: str
    output_hash: str
    creator_id: str
    accepted: bool
    signature: str
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuthorizationRecord:
    authorization_id: str
    creator_id: str
    domains: tuple[str, ...]
    operations: tuple[str, ...]
    asset_hashes: tuple[str, ...]
    issued_at: str
    expires_at: str | None
    signature: str
    version: str = "1"

    def unsigned_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("signature")
        data["domains"] = list(self.domains)
        data["operations"] = list(self.operations)
        data["asset_hashes"] = list(self.asset_hashes)
        return data

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signature": self.signature}


@dataclass(frozen=True)
class RevocationRecord:
    revocation_id: str
    authorization_id: str
    creator_id: str
    issued_at: str
    signature: str
    version: str = "1"

    def unsigned_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("signature")
        return data

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signature": self.signature}


@dataclass(frozen=True)
class RevocationState:
    creator_id: str
    sequence: int
    revocation_hashes: tuple[str, ...]
    previous_hash: str | None
    signature: str
    version: str = "1"

    def unsigned_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("signature")
        data["revocation_hashes"] = list(self.revocation_hashes)
        return data

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signature": self.signature}


@dataclass(frozen=True)
class CreatorManifest:
    """Compatibility shim for the original public manifest API."""

    creator_id: str
    display_name: str
    domain: str
    license_id: str
    version: str = "0.1.0"
    constraints: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.domain not in DOMAINS:
            raise ValueError("Unsupported domain")
        for field_name in ("creator_id", "display_name", "license_id", "version"):
            _require(getattr(self, field_name), field_name)


class GenerationBackend(Protocol):
    def capabilities(self) -> dict[str, Any]: ...
    def prepare(self, request: GenerationRequest) -> None: ...
    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult: ...
    def healthcheck(self) -> bool: ...
