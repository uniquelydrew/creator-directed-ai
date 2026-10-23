"""Fail-closed protocol for optional, locally provisioned model workers."""
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import CreativeSpecification, GenerationRequest, GenerationResult
from .registry import ModelRecord
from .store import ArtifactRef, ArtifactStore, canonical_json

PROTOCOL_VERSION = "1"


class AdapterError(RuntimeError):
    """A local learned-model adapter did not satisfy the protocol."""


@dataclass(frozen=True)
class ModelProvision:
    model_id: str
    revision: str
    manifest_hash: str
    files: tuple[dict[str, str], ...]
    version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "revision": self.revision, "manifest_hash": self.manifest_hash,
                "files": list(self.files), "version": self.version}


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_model(store: ArtifactStore, model: ModelRecord, source: str | Path) -> ArtifactRef:
    """Record hashes for a pre-downloaded model directory without network access."""
    root = Path(source).resolve()
    if not root.is_dir():
        raise AdapterError("model source must be an existing directory")
    files = tuple({"path": item.relative_to(root).as_posix(), "sha256": _digest_file(item)}
                  for item in sorted(root.rglob("*")) if item.is_file())
    if not files:
        raise AdapterError("model source contains no files")
    manifest_hash = hashlib.sha256(canonical_json(list(files))).hexdigest()
    provision = ModelProvision(model.model_id, model.revision, manifest_hash, files)
    return store.put_json(provision.to_dict())


def verify_model(model: ModelRecord, provision: ModelProvision, source: str | Path) -> None:
    root = Path(source).resolve()
    if not root.is_dir():
        raise AdapterError("model source must be an existing directory")
    if provision.model_id != model.model_id or provision.revision != model.revision:
        raise AdapterError("provisioned model does not match the selected registry record")
    actual = tuple({"path": item.relative_to(root).as_posix(), "sha256": _digest_file(item)}
                   for item in sorted(root.rglob("*")) if item.is_file())
    if not actual or hashlib.sha256(canonical_json(list(actual))).hexdigest() != provision.manifest_hash:
        raise AdapterError("local model files do not match the imported manifest")
    if model.expected_manifest_hash and provision.manifest_hash != model.expected_manifest_hash:
        raise AdapterError("local model manifest does not match the registry record")


class ProcessAdapter:
    """Runs a local worker using a one-request/one-response JSON protocol."""

    def __init__(self, command: Sequence[str], timeout_seconds: int = 300):
        if not command:
            raise ValueError("adapter command is required")
        self.command = tuple(command)
        self.timeout_seconds = timeout_seconds

    def generate(self, model: ModelRecord, model_path: str | Path, specification: CreativeSpecification,
                 request: GenerationRequest, authorized_assets: tuple[str, ...]) -> GenerationResult:
        with tempfile.TemporaryDirectory(prefix="creator-ai-adapter-") as output_dir:
            payload = {"protocol_version": PROTOCOL_VERSION, "model": model.adapter_dict(),
                       "model_path": str(Path(model_path).resolve()), "specification": specification.to_dict(),
                       "request": request.to_dict(), "authorized_asset_hashes": list(authorized_assets),
                       "output_dir": output_dir}
            env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "CREATOR_AI_OFFLINE": "1"}
            try:
                completed = subprocess.run(self.command, input=json.dumps(payload), text=True, capture_output=True,
                                           timeout=self.timeout_seconds, env=env, check=False)
            except subprocess.TimeoutExpired as exc:
                raise AdapterError("adapter timed out") from exc
            if completed.returncode:
                raise AdapterError("adapter exited unsuccessfully: " + completed.stderr.strip()[:500])
            try:
                response = json.loads(completed.stdout)
                filename = response["output_filename"]
                media_type = response["media_type"]
                metadata = response.get("metadata", {})
            except (TypeError, KeyError, json.JSONDecodeError) as exc:
                raise AdapterError("adapter returned an invalid response") from exc
            if not isinstance(filename, str) or not isinstance(media_type, str) or not isinstance(metadata, dict):
                raise AdapterError("adapter response has invalid field types")
            target = (Path(output_dir) / filename).resolve()
            if target.parent != Path(output_dir).resolve() or not target.is_file():
                raise AdapterError("adapter output must be a file directly inside its output directory")
            return GenerationResult(target.name, "process:" + model.adapter_id, model.model_id,
                                    {"protocol_version": PROTOCOL_VERSION, "runtime_version": model.runtime_version,
                                     **metadata}, target.read_bytes(), media_type)
