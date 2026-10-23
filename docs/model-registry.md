# Model registry and metadata-based license checks

The local JSON registry (`models/registry.json`) records model identifiers, immutable upstream revisions, declared SPDX license identifiers, supported domains, attribution, and consent requirements. The registry is versioned independently of model weights.

`ModelRegistry.load(path)` validates schema and metadata without network access. `LicensePolicy.evaluate(record, domain=..., consent_verified=...)` produces an explicit allow/deny decision and reasons. Unknown licenses are denied by default. A caller may configure its own license allowlist.

**Important limitation:** license identifiers are claims recorded in metadata, not cryptographic verification of licensing, training data rights, or legal permission. This release validates declared metadata and policy consistency **offline**; it does not fetch a live upstream model card, prove rights, validate model binaries, or supply evidence of consent. `consent_verified=True` must only be supplied after an independent authorization workflow. The default registry is an example record, not blanket approval for downstream use.

## Follow-up work

- Upstream license reconciliation with explicit provenance and recorded review dates
- Revision-bound weight checksums and secure model acquisition
- Signed creator authorization and revocation workflows
- Integrating registry policy into all backend execution paths
