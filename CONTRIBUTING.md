# Contributing

Run `python -m pip install -e '.[dev]'`, `python -m pytest -q`, `python -m ruff check .`, and `python -m mypy src/creator_ai` before opening a pull request. Do not add model weights, private creative assets, secrets, or generated creator artifacts to the repository. New backends must remain optional, must not download at import or inference time, and must produce provenance-compatible records.
