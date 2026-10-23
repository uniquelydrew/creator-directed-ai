# Model registry and metadata-based license checks

The local JSON registry (`models/registry.json`) records model identifiers, immutable upstream revisions, declared SPDX license identifiers, supported domains, attribution, and consent requirements. The registry is versioned independently of model weights.

`ModelRegistry.load(path)` validates schema and metadata without network access. `LicensePolicy.evaluate(record, domain=..., consent_verified=...)` produces an explicit allow/deny decision and reasons. Unknown licenses are denied by default. A caller may configure its own license allowlist.

**Important limitation:** license identifiers are claims recorded in metadata, not cryptographic verification of licensing, training data rights, or legal permission. This release validates declared metadata and policy consistency **offline**; it does not fetch a live upstream model card, prove rights, validate model binaries, or supply evidence of consent. `consent_verified=True` must only be supplied after an independent authorization workflow. The default registry is an example record, not blanket approval for downstream use.

## Learned adapter records

Learned records additionally declare an adapter identifier, runtime and hardware guidance, output media type, and whether identity-bearing creator consent is required. `creator-ai import-model --model MODEL --model-path DIRECTORY` creates a content-addressed manifest for files the user already downloaded; import never contacts a network. Generation rehashes the directory and refuses changed files.

The shipped examples are FLUX.1-schnell (Apache-2.0), MusicGen small (CC-BY-NC-4.0), and OpenVoice V2 (MIT). MusicGen is deliberately denied by the default permissive-license policy. A deployment owner must explicitly configure a policy allowlist only after its own license review. Voice cloning requires a signed authorization that covers the exact reference asset.
