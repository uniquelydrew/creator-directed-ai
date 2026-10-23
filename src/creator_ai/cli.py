"""Command line demo, model provisioning and registry validation."""
import argparse
from .core import CreatorManifest, GenerationRequest
from .backends import ReferenceBackend, TransformersTextBackend
from .provision import provision_text_model
from .registry import ModelRegistry
from .licensing import LicensePolicy


def main() -> None:
    parser = argparse.ArgumentParser(description="Creator-directed AI prototype")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--domain", choices=("visual", "writing", "music", "voice"), default="writing")
    parser.add_argument("--backend", choices=("reference", "text"), default="reference")
    parser.add_argument("--model", default=None, help="Reserved for future custom-model support")
    parser.add_argument("--registry", default="models/registry.json", help="Path to local model registry")
    args = parser.parse_args()
    if args.prompt == "validate-registry":
        registry = ModelRegistry.load(args.registry)
        policy = LicensePolicy()
        rejected = 0
        for model in registry.list():
            for domain in model.domains:
                decision = policy.evaluate(model, domain=domain)
                print(f"{model.model_id} [{domain}]: {'allowed' if decision.allowed else 'denied'}")
                for reason in decision.reasons:
                    print(f"  - {reason}")
                rejected += not decision.allowed
        if rejected:
            parser.exit(1, f"{rejected} registry policy check(s) denied\n")
        return
    if args.prompt == "provision-text":
        print(provision_text_model())
        return
    if not args.prompt:
        parser.error("a prompt, 'validate-registry', or 'provision-text' is required")
    manifest = CreatorManifest("demo", "Demo creator", args.domain, "demo-only")
    backend = ReferenceBackend() if args.backend == "reference" else TransformersTextBackend(args.model)
    print(backend.generate(manifest, GenerationRequest(args.prompt)).content)


if __name__ == "__main__":
    main()
