import pytest

from creator_ai.model_config import DEFAULT_TEXT_MODEL
from creator_ai.provision import find_cached_text_model


def test_model_is_pinned_and_license_recorded():
    assert len(DEFAULT_TEXT_MODEL.revision) == 40
    assert all(c in "0123456789abcdef" for c in DEFAULT_TEXT_MODEL.revision)
    assert DEFAULT_TEXT_MODEL.license_id == "Apache-2.0"


def test_offline_missing_cache_is_actionable(monkeypatch):
    import sys
    from types import ModuleType
    fake = ModuleType("huggingface_hub")
    def missing(**kwargs):
        assert kwargs["local_files_only"] is True
        raise OSError("missing")
    fake.snapshot_download = missing
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    with pytest.raises(RuntimeError, match="provision-text"):
        find_cached_text_model()
