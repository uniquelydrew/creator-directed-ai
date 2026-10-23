# Learned local adapters

Learned adapters are optional processes, not core-package dependencies. They receive one JSON object on standard input and write one JSON object to standard output. No log output may be written to standard output.

## Request and response

The request has `protocol_version: "1"`, `model` (registered ID, revision, adapter ID and runtime guidance), `model_path`, `specification`, `request`, `authorized_asset_hashes`, and a private `output_dir`. A worker must operate only on the supplied local model path and write its generated file directly inside `output_dir`.

The response is:

```json
{"output_filename":"result.png","media_type":"image/png","metadata":{"runtime":"diffusers","seed":42}}
```

The core rejects absolute paths, parent traversal, nested output paths, missing output files, malformed JSON, timeouts, and nonzero exits. It starts workers with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `CREATOR_AI_OFFLINE=1`.

## Model environments

Create one isolated environment per adapter and install its dependencies there. Recommended worker stacks are `diffusers`/PyTorch for `flux`, Transformers/PyTorch for `musicgen`, and the OpenVoice V2 runtime for `openvoice`. Pin those dependencies in the deployment-owned environment lockfile; do not add model runtimes or weights to the core package lockfile.

Before a run, download model files by your approved process, then import the resulting directory into the local store. `import-model` hashes every file and `adapter-healthcheck` rehashes it. The framework never downloads weights for learned adapters.

For OpenVoice, pass the immutable reference-audio asset hash in the generation request and ensure the signed voice authorization names that hash. Do not ship a public reference voice with an adapter.
