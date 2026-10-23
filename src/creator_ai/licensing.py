"""Deterministic metadata-based model usage policy, not legal advice."""
from dataclasses import dataclass
from .registry import ModelRecord


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LicensePolicy:
    """Allowlist applies to declared SPDX identifiers, not training data rights."""

    allowed_license_ids: frozenset[str] = frozenset({"Apache-2.0", "MIT", "BSD-3-Clause", "CC0-1.0"})

    def evaluate(self, model: ModelRecord, *, domain: str, consent_verified: bool = False) -> LicenseDecision:
        reasons: list[str] = []
        if model.license_id not in self.allowed_license_ids:
            reasons.append("License is not in the configured allowlist: " + model.license_id)
        if domain not in model.domains:
            reasons.append("Model does not declare support for domain: " + domain)
        if model.requires_consent and not consent_verified:
            reasons.append("Model requires independently verified creator consent")
        return LicenseDecision(not reasons, tuple(reasons))

    def require_allowed(self, model: ModelRecord, *, domain: str, consent_verified: bool = False) -> None:
        decision = self.evaluate(model, domain=domain, consent_verified=consent_verified)
        if not decision.allowed:
            raise PermissionError("; ".join(decision.reasons))
