"""Explicit pretrained model provisioning and local cache checks."""
from pathlib import Path
from .model_config import DEFAULT_TEXT_MODEL


def provision_text_model(cache_dir: str | None = None) -> str:
    """Download a pinned snapshot explicitly, never during inference."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install optional text dependencies first") from exc
    return snapshot_download(
        repo_id=DEFAULT_TEXT_MODEL.model_id,
        revision=DEFAULT_TEXT_MODEL.revision,
        cache_dir=cache_dir,
        allow_patterns=["*.json", "*.safetensors", "tokenizer.*", "vocab.json", "merges.txt", "special_tokens_map.json"],
    )


def find_cached_text_model(cache_dir: str | None = None) -> str:
    """Resolve only local files from the exact approved revision."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install optional text dependencies first") from exc
    try:
        return snapshot_download(
            repo_id=DEFAULT_TEXT_MODEL.model_id,
            revision=DEFAULT_TEXT_MODEL.revision,
            cache_dir=cache_dir,
            local_files_only=True,
            allow_patterns=["*.json", "*.safetensors", "tokenizer.*", "vocab.json", "merges.txt", "special_tokens_map.json"],
        )
    except Exception as exc:
        raise RuntimeError("Pinned text model is not cached. Run: creator-ai provision-text") from exc
