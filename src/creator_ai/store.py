"""Immutable local content-addressed storage."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


@dataclass(frozen=True)
class ArtifactRef:
    digest: str
    path: Path
    media_type: str


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put_bytes(self, data: bytes, media_type: str = "application/octet-stream") -> ArtifactRef:
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / "objects" / "sha256" / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise RuntimeError("content-addressed path collision")
        if not path.exists():
            path.write_bytes(data)
        return ArtifactRef(digest, path, media_type)

    def put_json(self, value: Any) -> ArtifactRef:
        return self.put_bytes(canonical_json(value), "application/json")

    def read_bytes(self, digest: str) -> bytes:
        path = self.root / "objects" / "sha256" / digest[:2] / digest
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("artifact hash does not match its content")
        return data

    def read_json(self, digest: str) -> Any:
        return json.loads(self.read_bytes(digest))
