import pytest
from creator_ai.core import CreatorManifest, GenerationRequest
from creator_ai.backends import ReferenceBackend


@pytest.mark.parametrize("domain", ["visual", "writing", "music", "voice"])
def test_reference_generation_is_repeatable(domain):
    manifest = CreatorManifest("artist", "Artist", domain, "demo-only")
    backend = ReferenceBackend()
    request = GenerationRequest("test", 123)
    assert backend.generate(manifest, request) == backend.generate(manifest, request)


def test_invalid_domain_rejected():
    with pytest.raises(ValueError):
        ReferenceBackend().generate(
            CreatorManifest("artist", "Artist", "unknown", "demo-only"),
            GenerationRequest("test"),
        )
