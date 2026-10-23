"""Audited built-in text model reference (weights are external)."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DefaultTextModel:
    model_id: str = "HuggingFaceTB/SmolLM2-135M-Instruct"
    revision: str = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
    license_id: str = "Apache-2.0"
    source_url: str = "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct"

DEFAULT_TEXT_MODEL = DefaultTextModel()
