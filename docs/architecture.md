# Architecture (initial prototype)

Creator manifests describe ownership, domain, license identifier, and constraints. Generation backends implement a common protocol. The reference backend is deterministic and runs offline; it is **not** a trained model.

The optional Transformers text backend loads a separately provisioned **pinned** SmolLM2-135M-Instruct snapshot. Normal inference is local-only. See [model licensing](model-licensing.md).

## Planned extensions
- Versioned schema validation and generalized model registry
- Asset provenance and rights verification
- Domain-specific conditioning, adapters, and evaluations
- Explicit approval and certification records
- Expanded compatibility and model provisioning

No model weights or artist datasets are bundled with the framework. Model licensing and generated-output rights must be evaluated separately.
