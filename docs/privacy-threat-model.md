# Privacy and threat model

Creator assets, passphrase-encrypted Ed25519 signing keys, authorization records, and generated artifacts remain in a user-selected local workspace. The framework does not upload assets, emit telemetry, or download models during import or inference. Model installation is an explicit command.

Threats addressed include accidental use after local authorization revocation, altered artifacts, unsigned approvals, and unapproved model metadata. SHA-256 artifact references detect content changes; Ed25519 signatures authenticate records held by a creator key. These controls do not protect a compromised machine, recover distributed weights, or establish legal ownership.

Revocations are stored as signed, hash-linked state records. A missing, malformed, or signature-invalid referenced record fails closed. A local-only system cannot detect a filesystem rollback to an older valid state without an external trusted timestamp or witness; deployments requiring that assurance must provide one.
