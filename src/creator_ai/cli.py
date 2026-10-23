"""Offline CLI for model provisioning, validation, and creator workflow demos."""
import argparse
import getpass
import json
import shlex
from pathlib import Path

from .adapters import ModelProvision, import_model, verify_model
from .auth import create_authorization, create_key, load_private_key
from .backends import ReferenceBackend, TransformersTextBackend
from .core import CreativeSpecification, CreatorIdentity, CreatorManifest, GenerationRequest
from .licensing import LicensePolicy
from .provision import provision_text_model
from .registry import ModelRegistry
from .workflow import CreatorWorkspace


def _registry(path: str) -> int:
    rejected = 0
    for model in ModelRegistry.load(path).list():
        for domain in model.domains:
            decision = LicensePolicy().evaluate(model, domain=domain)
            print(f"{model.model_id} [{domain}]: {'allowed' if decision.allowed else 'denied'}")
            for reason in decision.reasons:
                print(f"  - {reason}")
            rejected += not decision.allowed
    return rejected


def _workflow(args: argparse.Namespace) -> None:
    key_path = Path(args.key)
    passphrase = getpass.getpass("Creator key passphrase: ")
    if key_path.exists():
        private = load_private_key(key_path, passphrase)
        public = private.public_key().public_bytes_raw().hex()
        import base64
        identity = CreatorIdentity(args.creator_id, args.creator_name, base64.b64encode(bytes.fromhex(public)).decode())
    else:
        created = create_key(key_path, passphrase)
        identity = CreatorIdentity(args.creator_id, args.creator_name, created.public_key)
        private = load_private_key(key_path, passphrase)
    workspace = CreatorWorkspace(args.workspace)
    workspace.register_creator(identity)
    authorization = create_authorization(identity, private, (args.domain,), ("generate", "export", "approve"))
    authorization_ref = workspace.store_authorization(authorization)
    specification = CreativeSpecification(args.domain, args.title, json.loads(args.constraints))
    command = tuple(shlex.split(args.adapter_command)) if args.adapter_command else None
    generation_ref, output = workspace.generate(identity, authorization_ref.digest, specification,
                                                GenerationRequest(args.prompt, args.seed, specification), ModelRegistry.load(args.registry),
                                                model_id=args.model, model_path=args.model_path,
                                                provision_hash=args.provision, adapter_command=command)
    generation = workspace._load_generation(generation_ref.digest)
    workspace.evaluate(generation_ref.digest, True, "offline deterministic demonstration")
    approval_ref = workspace.approve(generation_ref.digest, authorization_ref.digest, identity, private)
    destination = Path(args.output) if args.output else Path(args.workspace) / f"{generation.record_id}.{ {'visual':'svg','music':'mid','voice':'wav','writing':'txt'}[args.domain] }"
    workspace.export(generation_ref.digest, authorization_ref.digest, approval_ref.digest, identity, destination)
    print(json.dumps({"generation_id": generation.record_id, "output_hash": output.digest, "output": str(destination)}, sort_keys=True))


def _import_model(args: argparse.Namespace) -> None:
    workspace = CreatorWorkspace(args.workspace)
    ref = import_model(workspace.store, ModelRegistry.load(args.registry).get(args.model), args.model_path)
    print(json.dumps({"model_id": args.model, "provision_hash": ref.digest}, sort_keys=True))


def _healthcheck(args: argparse.Namespace) -> None:
    try:
        provision = ModelProvision(**CreatorWorkspace(args.workspace).store.read_json(args.provision))
        verify_model(ModelRegistry.load(args.registry).get(args.model), provision, args.model_path)
    except Exception as exc:
        raise SystemExit("adapter healthcheck failed: " + str(exc)) from exc
    print("adapter healthcheck passed")


def _inspect_provenance(args: argparse.Namespace) -> None:
    print(json.dumps(CreatorWorkspace(args.workspace).store.read_json(args.generation_hash), sort_keys=True, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Creator-directed AI local-first framework")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--domain", choices=("visual", "writing", "music", "voice"), default="writing")
    parser.add_argument("--backend", choices=("reference", "text"), default="reference")
    parser.add_argument("--model", default=None, help="Registered learned model ID")
    parser.add_argument("--model-path", default=None, help="Pre-downloaded local model directory")
    parser.add_argument("--provision", default=None, help="Immutable model-provision artifact digest")
    parser.add_argument("--adapter-command", default=None, help="Local worker command; no model download is performed")
    parser.add_argument("--registry", default="models/registry.json", help="Path to local model registry")
    parser.add_argument("--workflow", action="store_true", help="Run a signed, policy-gated offline workflow")
    parser.add_argument("--workspace", default=".creator-ai", help="Local immutable artifact store")
    parser.add_argument("--key", default="creator-key.pem", help="Encrypted Ed25519 private-key file")
    parser.add_argument("--creator-id", default="demo")
    parser.add_argument("--creator-name", default="Demo creator")
    parser.add_argument("--title", default="Untitled specification")
    parser.add_argument("--constraints", default="{}", help="JSON object of domain constraints")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", default=None)
    parser.add_argument("--generation-hash", default=None)
    args = parser.parse_args(argv)
    if args.prompt == "validate-registry":
        if _registry(args.registry):
            parser.exit(1, "registry policy checks denied\n")
        return
    if args.prompt == "provision-text":
        print(provision_text_model())
        return
    if args.prompt == "import-model":
        if not args.model or not args.model_path:
            parser.error("import-model requires --model and --model-path")
        _import_model(args)
        return
    if args.prompt == "adapter-healthcheck":
        if not args.model or not args.model_path or not args.provision:
            parser.error("adapter-healthcheck requires --model, --model-path, and --provision")
        _healthcheck(args)
        return
    if args.prompt == "inspect-provenance":
        if not args.generation_hash:
            parser.error("inspect-provenance requires --generation-hash")
        _inspect_provenance(args)
        return
    if not args.prompt:
        parser.error("a prompt or lifecycle command is required")
    if args.workflow:
        _workflow(args)
        return
    manifest = CreatorManifest("demo", "Demo creator", args.domain, "demo-only")
    backend = ReferenceBackend() if args.backend == "reference" else TransformersTextBackend(args.model)
    print(backend.generate(manifest, GenerationRequest(args.prompt, args.seed)).content)


if __name__ == "__main__":
    main()
