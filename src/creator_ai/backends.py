"""Reference and optional pretrained backends."""
import hashlib
from .core import CreatorManifest, GenerationRequest, GenerationResult
from .model_config import DEFAULT_TEXT_MODEL
from .provision import find_cached_text_model


class ReferenceBackend:
    """Deterministic, offline, non-ML demonstration backend."""

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        digest = hashlib.sha256(
            f"{manifest.creator_id}:{manifest.domain}:{request.prompt}:{request.seed}".encode()
        ).hexdigest()[:12]
        return GenerationResult(
            content=f"[reference:{manifest.domain}:{digest}] {request.prompt}",
            backend="reference",
            model_id="deterministic-v1",
            metadata={"notice": "Reference output only; not AI-generated creative work."},
        )


class TransformersTextBackend:
    """Pinned default text inference; never downloads at inference time."""

    def __init__(self, model_id: str | None = None):
        if model_id is not None and model_id != DEFAULT_TEXT_MODEL.model_id:
            raise ValueError("Custom model provisioning is not yet supported")
        self.model_id = DEFAULT_TEXT_MODEL.model_id

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        if manifest.domain != "writing":
            raise ValueError("Text backend supports writing only")
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("Install with: pip install 'creator-directed-ai[text]'") from exc
        local_path = find_cached_text_model()
        generator = pipeline("text-generation", model=local_path, tokenizer=local_path, device="cpu")
        messages = [{"role": "user", "content": request.prompt}]
        output = generator(messages, max_new_tokens=96, do_sample=False)
        generated = output[0]["generated_text"]
        if isinstance(generated, list):
            generated = generated[-1]["content"]
        return GenerationResult(
            content=generated,
            backend="transformers",
            model_id=self.model_id,
            metadata={"revision": DEFAULT_TEXT_MODEL.revision, "license": DEFAULT_TEXT_MODEL.license_id},
        )
