# Creator-Directed AI

Local-first, open-source foundation for creator-governed generative systems across **visual art, writing, music, and voice acting**.

**Status:** Early prototype. The offline reference backend demonstrates interfaces but does not perform machine-learning generation.

## Quick start

```bash
python -m pip install -e '.[dev]'
creator-ai "A forest at dawn" --domain visual
pytest -q
```

## Optional real text generation

```bash
python -m pip install -e '.[text]'
creator-ai provision-text
creator-ai "Write a short opening paragraph" --domain writing --backend text
```

The default model is **HuggingFaceTB/SmolLM2-135M-Instruct**, pinned to a specific upstream commit. Weights are not bundled. The explicit provisioning command downloads them once; generation uses the cached files only and never downloads implicitly.

See [model provisioning and licensing](docs/model-licensing.md) and [architecture](docs/architecture.md).

## Principles

- Creator-owned assets and permissions are distinct from framework licensing.
- All four domains share a manifest and generation contract.
- Offline deterministic reference backend works without model downloads.
- Optional pretrained backends are separately installed.
- No mandatory hosted service or centralized account.
