# Architecture

Creator manifests describe ownership, domain, license identifier, and constraints. Generation backends implement a common protocol. The reference backend is deterministic and runs offline; it is **not** a trained model.

The optional Transformers text backend loads a separately provisioned **pinned** SmolLM2-135M-Instruct snapshot. Normal inference is local-only. See [model licensing](model-licensing.md).

## Optional learned adapters

Learned visual, music, and voice adapters run as isolated local processes using a versioned JSON request/result protocol. Core policy validates the actual registered model, signed authorization, and immutable local model-file manifest before the worker starts. Workers receive an offline-only environment and cannot provision or download weights.

Install model runtimes in dedicated environments, import a pre-downloaded model directory with `creator-ai import-model`, then pass its provision digest, local path, and worker command to a signed workflow. The deterministic reference backends remain the portable default.

Voice cloning additionally requires a signed voice-domain authorization that names the immutable reference-asset hash. This is a provenance and authorization control, not legal proof of identity, ownership, or consent.

No model weights or artist datasets are bundled with the framework. Model licensing and generated-output rights must be evaluated separately.
