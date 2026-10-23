"""Entry point contract for isolated learned-model worker environments.

Install each adapter's dependencies in its own environment; this module never
downloads weights and intentionally refuses unknown adapter identifiers.
"""
import json
import sys
from pathlib import Path
from typing import Any


def _request() -> dict[str, Any]:
    raw = json.load(sys.stdin)
    if not isinstance(raw, dict):
        raise TypeError("request must be an object")
    if raw.get("protocol_version") != "1":
        raise ValueError("unsupported adapter protocol")
    if not Path(raw["model_path"]).is_dir() or not Path(raw["output_dir"]).is_dir():
        raise ValueError("model_path and output_dir must be local directories")
    return raw


def main() -> None:
    request = _request()
    adapter_id = request["model"]["adapter_id"]
    # Worker environments are deliberately external to the core package.  Their
    # launchers must implement this same one-shot protocol and may be selected
    # through --adapter-command; this dispatcher fails closed when not installed.
    raise RuntimeError(f"{adapter_id} worker dependencies are not installed in this environment")


if __name__ == "__main__":
    main()
