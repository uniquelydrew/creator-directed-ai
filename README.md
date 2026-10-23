# Creator-Directed AI

Local-first, open-source foundation for creator-governed generative systems across **visual art, writing, music, and voice acting**.

**Status:** v0.1 local-first foundation. Four deterministic, offline workflows produce writing, SVG art, MIDI music, and WAV performance-direction placeholders with signed provenance.

## Quick start

```bash
python -m pip install -e '.[dev]'
creator-ai "A forest at dawn" --domain visual
pytest -q
```

## Signed offline workflow

The following performs creator registration, authorization, policy-gated generation, evaluation, approval, and certified export entirely locally. Keep the passphrase out of shell history in real use.

```bash
creator-ai "A forest at dawn" --workflow --domain visual --workspace .creator-ai \
  --key creator-key.pem --title "Dawn study" --output dawn.svg
```

The CLI requests the key passphrase interactively; it does not accept it as a command-line argument.

The same command supports `writing`, `music`, and `voice`. Its deterministic outputs are text, SVG, MIDI, and WAV respectively; they are reference demonstrations rather than trained creator models.

## Optional real text generation

```bash
python -m pip install -e '.[text]'
creator-ai provision-text
creator-ai "Write a short opening paragraph" --domain writing --backend text
```

The default model is **HuggingFaceTB/SmolLM2-135M-Instruct**, pinned to a specific upstream commit. Weights are not bundled. The explicit provisioning command downloads them once; generation uses the cached files only and never downloads implicitly.

## Optional learned adapters

Visual, music, and authorized voice-cloning adapters use isolated local worker processes. Download and install model runtimes separately, then import only an existing local model directory:

```bash
creator-ai import-model --model black-forest-labs/FLUX.1-schnell --model-path D:\models\flux --workspace .creator-ai
creator-ai adapter-healthcheck --model black-forest-labs/FLUX.1-schnell --model-path D:\models\flux --provision PROVISION_HASH --workspace .creator-ai
```

Workers must implement the documented one-request JSON protocol and are passed with `--adapter-command`; they run with offline flags and cannot trigger provisioning. Learned runtimes may need a CUDA GPU. The portable Python 3.10–3.12 promise continues to apply to deterministic workflows. MusicGen is present for registry/protocol testing but is denied by the default license policy; OpenVoice requires a signed authorization covering the reference voice asset.

See [model provisioning and licensing](docs/model-licensing.md) and [architecture](docs/architecture.md).
See [platform support](docs/support.md), the [privacy and threat model](docs/privacy-threat-model.md), and [model registry](docs/model-registry.md).

## Principles

- Creator-owned assets and permissions are distinct from framework licensing.
- All four domains share a manifest and generation contract.
- Offline deterministic reference backend works without model downloads.
- Optional pretrained backends are separately installed.
- No mandatory hosted service or centralized account.
