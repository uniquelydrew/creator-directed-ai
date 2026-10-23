# Default text model licensing and provisioning

Model: [HuggingFaceTB/SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct)

Pinned Hugging Face repository commit: `12fd25f77366fa6b3b4b768ec3050bf629380bac`

Upstream model card and Hugging Face model API identify the license as **Apache-2.0** (verified 2026-10-23). This is an upstream license declaration, not a legal audit of every training-data right or generated output. The model's weights are **not redistributed** with this framework.

The framework itself is separately licensed under Apache-2.0. Users are responsible for reviewing the upstream model license and their intended usage. Future models will need separate validation.

## Provision once

```bash
pip install -e '.[text]'
creator-ai provision-text
```

Provisioning downloads the exact pinned revision into the Hugging Face cache. Normal inference resolves the cached snapshot with `local_files_only=True` and fails with a provisioning instruction if unavailable. Set `HF_HOME` before provisioning and inference to choose the cache root.

## Offline

After provisioning, disconnect from the network and run:

```bash
creator-ai "Write a paragraph about a forest" --backend text
```

The model is small (approximately 135M parameters), but it is an experimental baseline, not a production-quality author model. CPU inference can be slow; RAM use exceeds raw weight size due to framework overhead. An actual model smoke test requires optional ML dependencies and provisioned weights.
