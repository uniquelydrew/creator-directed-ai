"""Deterministic offline and optional pretrained generation backends."""
import hashlib
import html
import math
import re
import struct
import wave
from io import BytesIO
from typing import Any, cast

from .core import CreatorManifest, GenerationRequest, GenerationResult
from .model_config import DEFAULT_TEXT_MODEL
from .provision import find_cached_text_model


class _OfflineBackend:
    def prepare(self, request: GenerationRequest) -> None:
        request.to_dict()

    def healthcheck(self) -> bool:
        return True


class ReferenceBackend(_OfflineBackend):
    """Deterministic writing baseline with no model weights or network access."""

    model_id = "local/deterministic-v1"

    def capabilities(self) -> dict[str, Any]:
        return {"domains": ["writing"], "offline": True, "media_type": "text/plain"}

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        self.prepare(request)
        digest = hashlib.sha256(f"{manifest.creator_id}:{manifest.domain}:{request.prompt}:{request.seed}".encode()).hexdigest()[:12]
        return GenerationResult(f"[reference:{manifest.domain}:{digest}] {request.prompt}", "reference", self.model_id, {"offline": True})


class SvgBackend(_OfflineBackend):
    model_id = "local/deterministic-svg-v1"

    def capabilities(self) -> dict[str, Any]:
        return {"domains": ["visual"], "offline": True, "media_type": "image/svg+xml"}

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        if manifest.domain != "visual":
            raise ValueError("SVG backend supports visual only")
        self.prepare(request)
        constraints = request.specification.constraints if request.specification else {}
        palette = constraints.get("palette", ["#15304a", "#e7b75f", "#f5efe1"])
        if not isinstance(palette, list) or len(palette) < 2 or not all(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in palette):
            raise ValueError("visual palette must contain at least two colors")
        token = int(hashlib.sha256(f"{request.prompt}:{request.seed}".encode()).hexdigest()[:8], 16)
        x, y = 40 + token % 220, 40 + (token >> 8) % 220
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">'
               f'<rect width="400" height="300" fill="{palette[0]}"/><circle cx="{x}" cy="{y}" r="{45 + token % 70}" fill="{palette[1]}"/>'
               f'<path d="M0 260 L120 {150 + token % 70} L230 250 L400 100 V300 H0Z" fill="{palette[-1]}"/>'
               f'<text x="18" y="282" font-size="12" fill="#111">{html.escape(request.prompt)}</text></svg>')
        return GenerationResult(svg, "svg", self.model_id, {"offline": True}, svg.encode(), "image/svg+xml")


class MidiBackend(_OfflineBackend):
    model_id = "local/deterministic-midi-v1"

    def capabilities(self) -> dict[str, Any]:
        return {"domains": ["music"], "offline": True, "media_type": "audio/midi"}

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        if manifest.domain != "music":
            raise ValueError("MIDI backend supports music only")
        self.prepare(request)
        constraints = request.specification.constraints if request.specification else {}
        tempo = int(constraints.get("tempo", 120))
        if not 30 <= tempo <= 300:
            raise ValueError("tempo must be between 30 and 300")
        notes = [60 + ((request.seed + offset) % 12) for offset in (0, 4, 7, 12)]
        events = bytearray(b"\x00\xFF\x51\x03" + int(60_000_000 / tempo).to_bytes(3, "big"))
        for note in notes:
            events.extend(b"\x00\x90" + bytes([note, 80]) + b"\x60\x80" + bytes([note, 0]))
        events.extend(b"\x00\xFF\x2F\x00")
        midi = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60MTrk" + len(events).to_bytes(4, "big") + bytes(events)
        return GenerationResult(f"tempo={tempo}; notes={','.join(map(str, notes))}; prompt={request.prompt}", "midi", self.model_id, {"tempo": tempo, "notes": notes}, midi, "audio/midi")


class WavBackend(_OfflineBackend):
    model_id = "local/deterministic-wav-v1"

    def capabilities(self) -> dict[str, Any]:
        return {"domains": ["voice"], "offline": True, "media_type": "audio/wav"}

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        if manifest.domain != "voice":
            raise ValueError("WAV backend supports voice only")
        self.prepare(request)
        rate, frequency = 8_000, 220 + request.seed % 330
        buffer = BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
            output.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * frequency * i / rate))) for i in range(rate)))
        return GenerationResult(f"offline performance-direction placeholder at {frequency}Hz: {request.prompt}", "wav", self.model_id, {"frequency_hz": frequency}, buffer.getvalue(), "audio/wav")


class TransformersTextBackend:
    """Pinned default text inference; never downloads at inference time."""
    def __init__(self, model_id: str | None = None):
        if model_id is not None and model_id != DEFAULT_TEXT_MODEL.model_id:
            raise ValueError("Custom model provisioning is not yet supported")
        self.model_id = DEFAULT_TEXT_MODEL.model_id

    def capabilities(self) -> dict[str, Any]:
        return {"domains": ["writing"], "offline": True, "media_type": "text/plain"}

    def prepare(self, request: GenerationRequest) -> None:
        request.to_dict(); find_cached_text_model()

    def healthcheck(self) -> bool:
        try:
            find_cached_text_model()
        except RuntimeError:
            return False
        return True

    def generate(self, manifest: CreatorManifest, request: GenerationRequest) -> GenerationResult:
        manifest.validate()
        if manifest.domain != "writing":
            raise ValueError("Text backend supports writing only")
        try:
            # Learned text generation is an optional adapter and is not part of
            # the deterministic offline CI dependency set.
            from importlib import import_module
            pipeline = import_module("transformers").pipeline
        except ImportError as exc:
            raise RuntimeError("Install with: pip install 'creator-directed-ai[text]'") from exc
        local_path = find_cached_text_model()
        output = pipeline("text-generation", model=local_path, tokenizer=local_path, device="cpu")([{"role": "user", "content": request.prompt}], max_new_tokens=96, do_sample=False)
        generated = cast(Any, output[0]["generated_text"])
        if isinstance(generated, list):
            generated = generated[-1]["content"]
        return GenerationResult(generated, "transformers", self.model_id, {"revision": DEFAULT_TEXT_MODEL.revision, "license": DEFAULT_TEXT_MODEL.license_id})


def deterministic_backend(domain: str) -> Any:
    return {"writing": ReferenceBackend, "visual": SvgBackend, "music": MidiBackend, "voice": WavBackend}[domain]()
