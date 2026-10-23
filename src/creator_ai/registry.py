"""Offline model registry with explicit, auditable metadata."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class RegistryError(ValueError):
    """Invalid or conflicting model registry metadata."""


@dataclass(frozen=True)
class ModelRecord:
    model_id: str
    revision: str
    license_id: str
    domains: tuple[str, ...]
    source_url: str
    license_url: str
    attribution: str = ""
    requires_consent: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    adapter_id: str = ""
    expected_manifest_hash: str = ""
    runtime_version: str = ""
    hardware: str = ""
    media_type: str = ""
    requires_identity_consent: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ModelRecord":
        required = {"model_id", "revision", "license_id", "domains", "source_url", "license_url"}
        missing = required - raw.keys()
        if missing:
            raise RegistryError("Missing required fields: " + ", ".join(sorted(missing)))
        optional = {"attribution", "requires_consent", "metadata", "adapter_id", "expected_manifest_hash",
                    "runtime_version", "hardware", "media_type", "requires_identity_consent"}
        unknown = set(raw) - (required | optional)
        if unknown:
            raise RegistryError("Unknown fields: " + ", ".join(sorted(unknown)))
        if not isinstance(raw["domains"], list) or not raw["domains"] or not all(isinstance(x, str) for x in raw["domains"]):
            raise RegistryError("domains must be a nonempty list of strings")
        if not isinstance(raw.get("requires_consent", False), bool):
            raise RegistryError("requires_consent must be a boolean")
        if not isinstance(raw.get("metadata", {}), dict):
            raise RegistryError("metadata must be an object")
        try:
            record = cls(
                model_id=raw["model_id"], revision=raw["revision"],
                license_id=raw["license_id"], domains=tuple(raw["domains"]),
                source_url=raw["source_url"], license_url=raw["license_url"],
                attribution=raw.get("attribution", ""),
                requires_consent=raw.get("requires_consent", False),
                metadata=raw.get("metadata", {}),
                adapter_id=raw.get("adapter_id", ""), expected_manifest_hash=raw.get("expected_manifest_hash", ""),
                runtime_version=raw.get("runtime_version", ""), hardware=raw.get("hardware", ""),
                media_type=raw.get("media_type", ""), requires_identity_consent=raw.get("requires_identity_consent", False),
            )
        except (TypeError, KeyError) as exc:
            raise RegistryError("Invalid model record types") from exc
        record.validate()
        return record

    def validate(self) -> None:
        if not isinstance(self.model_id, str) or not _ID.fullmatch(self.model_id):
            raise RegistryError("model_id must be an owner/repository identifier")
        if not isinstance(self.revision, str) or not _COMMIT.fullmatch(self.revision):
            raise RegistryError("revision must be a full lowercase 40-character commit SHA")
        if not isinstance(self.license_id, str) or not self.license_id.strip():
            raise RegistryError("license_id is required")
        if any(d not in {"visual", "writing", "music", "voice"} for d in self.domains):
            raise RegistryError("Unsupported model domain")
        if not all(isinstance(u, str) and u.startswith("https://") for u in (self.source_url, self.license_url)):
            raise RegistryError("source_url and license_url must use HTTPS")
        if not isinstance(self.attribution, str):
            raise RegistryError("attribution must be text")
        if not all(isinstance(value, str) for value in (self.adapter_id, self.expected_manifest_hash, self.runtime_version, self.hardware, self.media_type)):
            raise RegistryError("adapter metadata must be text")
        if self.expected_manifest_hash and not re.fullmatch(r"[0-9a-f]{64}", self.expected_manifest_hash):
            raise RegistryError("expected_manifest_hash must be a SHA-256 digest")
        if not isinstance(self.requires_identity_consent, bool):
            raise RegistryError("requires_identity_consent must be a boolean")

    def adapter_dict(self) -> dict[str, Any]:
        """Stable, minimal model metadata supplied to an isolated worker."""
        if not self.adapter_id:
            raise RegistryError("model has no learned adapter")
        return {"model_id": self.model_id, "revision": self.revision, "adapter_id": self.adapter_id,
                "runtime_version": self.runtime_version, "hardware": self.hardware, "media_type": self.media_type,
                "requires_identity_consent": self.requires_identity_consent}


class ModelRegistry:
    def __init__(self, records: tuple[ModelRecord, ...]):
        ids = [r.model_id for r in records]
        if len(set(ids)) != len(ids):
            raise RegistryError("Duplicate model_id")
        self._records = {r.model_id: r for r in records}

    @classmethod
    def load(cls, path: str | Path) -> "ModelRegistry":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RegistryError("Cannot read model registry") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("models"), list):
            raise RegistryError("Expected schema_version=1 and models array")
        return cls(tuple(ModelRecord.from_dict(item) for item in data["models"]))

    def get(self, model_id: str) -> ModelRecord:
        try:
            return self._records[model_id]
        except KeyError as exc:
            raise RegistryError("Unregistered model: " + model_id) from exc

    def list(self) -> tuple[ModelRecord, ...]:
        return tuple(self._records.values())
