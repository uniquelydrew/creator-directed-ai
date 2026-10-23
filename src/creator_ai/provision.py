"""Explicit pretrained model provisioning and local cache checks."""
from .model_config import DEFAULT_TEXT_MODEL


def provision_text_model(cache_dir: str | None = None) -> str:
    """Download a pinned snapshot explicitly, never during inference."""
    try:
        # The text backend is optional; CI deliberately validates the local-first
        # baseline without installing its network/model dependencies.
        from importlib import import_module
        snapshot_download = import_module("huggingface_hub").snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install optional text dependencies first") from exc
    return str(
        snapshot_download(
            repo_id=DEFAULT_TEXT_MODEL.model_id,
            revision=DEFAULT_TEXT_MODEL.revision,
            cache_dir=cache_dir,
            allow_patterns=["*.json", "*.safetensors", "tokenizer.*", "vocab.json", "merges.txt", "special_tokens_map.json"],
        )
    )


def find_cached_text_model(cache_dir: str | None = None) -> str:
    """Resolve only local files from the exact approved revision."""
    try:
        # See provision_text_model: this optional dependency is absent from the
        # deterministic, offline CI environment.
        from importlib import import_module
        snapshot_download = import_module("huggingface_hub").snapshot_download
    except ImportError as exc:
        raise RuntimeError("Install optional text dependencies first") from exc
    try:
        return str(
            snapshot_download(
                repo_id=DEFAULT_TEXT_MODEL.model_id,
                revision=DEFAULT_TEXT_MODEL.revision,
                cache_dir=cache_dir,
                local_files_only=True,
                allow_patterns=["*.json", "*.safetensors", "tokenizer.*", "vocab.json", "merges.txt", "special_tokens_map.json"],
            )
        )
    except Exception as exc:
        raise RuntimeError("Pinned text model is not cached. Run: creator-ai provision-text") from exc
