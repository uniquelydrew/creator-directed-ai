"""Command line demo and explicit model provisioning."""
import argparse
from .core import CreatorManifest, GenerationRequest
from .backends import ReferenceBackend, TransformersTextBackend
from .provision import provision_text_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Creator-directed AI prototype")
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--domain", choices=("visual", "writing", "music", "voice"), default="writing")
    parser.add_argument("--backend", choices=("reference", "text"), default="reference")
    parser.add_argument("--model", default=None, help="Reserved for future custom-model support")
    args = parser.parse_args()
    if args.prompt == "provision-text":
        print(provision_text_model())
        return
    if not args.prompt:
        parser.error("a prompt or 'provision-text' is required")
    manifest = CreatorManifest("demo", "Demo creator", args.domain, "demo-only")
    backend = ReferenceBackend() if args.backend == "reference" else TransformersTextBackend(args.model)
    print(backend.generate(manifest, GenerationRequest(args.prompt)).content)


if __name__ == "__main__":
    main()
