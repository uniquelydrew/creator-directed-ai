"""Local Ed25519 signing, encrypted key files, and authorization checks."""
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .core import AuthorizationRecord, CreatorIdentity, RevocationRecord
from .store import canonical_json


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_key(path: str | Path, passphrase: str) -> CreatorIdentity:
    if not passphrase:
        raise ValueError("passphrase is required")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(passphrase.encode())))
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return CreatorIdentity(path.stem, path.stem, base64.b64encode(public).decode())


def load_private_key(path: str | Path, passphrase: str) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), passphrase.encode())
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("key is not Ed25519")
    return key


def sign(private: Ed25519PrivateKey, payload: dict[str, Any]) -> str:
    return base64.b64encode(private.sign(canonical_json(payload))).decode()


def verify(public_key: str, payload: dict[str, Any], signature: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(base64.b64decode(signature), canonical_json(payload))
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def create_authorization(identity: CreatorIdentity, private: Ed25519PrivateKey, domains: tuple[str, ...], operations: tuple[str, ...], asset_hashes: tuple[str, ...] = (), expires_at: str | None = None) -> AuthorizationRecord:
    authorization_id = str(uuid4())
    issued_at = now()
    unsigned: dict[str, Any] = {"authorization_id": authorization_id, "creator_id": identity.creator_id, "domains": list(domains), "operations": list(operations), "asset_hashes": list(asset_hashes), "issued_at": issued_at, "expires_at": expires_at, "version": "1"}
    return AuthorizationRecord(authorization_id, identity.creator_id, domains, operations, asset_hashes, issued_at, expires_at, sign(private, unsigned))


def revoke_authorization(identity: CreatorIdentity, private: Ed25519PrivateKey, authorization_id: str) -> RevocationRecord:
    unsigned = {"revocation_id": str(uuid4()), "authorization_id": authorization_id, "creator_id": identity.creator_id, "issued_at": now(), "version": "1"}
    return RevocationRecord(unsigned["revocation_id"], authorization_id, identity.creator_id, unsigned["issued_at"], sign(private, unsigned))


def authorization_allowed(record: AuthorizationRecord, identity: CreatorIdentity, domain: str, operation: str, asset_hashes: tuple[str, ...] = (), revoked: set[str] | None = None) -> None:
    if not verify(identity.public_key, record.unsigned_dict(), record.signature):
        raise PermissionError("authorization signature is invalid")
    if record.creator_id != identity.creator_id:
        raise PermissionError("authorization belongs to a different creator")
    if revoked and record.authorization_id in revoked:
        raise PermissionError("authorization has been revoked")
    if domain not in record.domains or operation not in record.operations:
        raise PermissionError("authorization does not permit this operation")
    if not set(asset_hashes).issubset(record.asset_hashes):
        raise PermissionError("authorization does not permit one or more assets")
    if record.expires_at and datetime.fromisoformat(record.expires_at) <= datetime.now(timezone.utc):
        raise PermissionError("authorization has expired")
