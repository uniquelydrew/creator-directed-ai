"""Portable creator packages and backend protocol."""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CreatorManifest:
    creator_id: str
    display_name: str
    domain: str
    license_id: str
    version: str = "0.1.0"
    constraints: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.domain not in {"visual", "writing", "music", "voice"}:
            raise ValueError("Unsupported domain")
        if not all((self.creator_id, self.display_name, self.license_id, self.version)):
            raise ValueError("Manifest fields must be non-empty")


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    seed: int = 0


@dataclass(frozen=True)
class GenerationResult:
    content: str
    backend: str
    model_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class GenerationBackend(Protocol):
    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult: ...
