# Platform and hardware support

The deterministic workflows are supported on Python 3.10 through 3.12 on Windows, macOS, and Linux with a normal CPU installation. They require no GPU, network access, model weights, or hosted account. CI covers Windows and Linux; macOS is supported by the same pure-Python runtime path.

The optional Transformers text backend requires its separately installed dependencies and a previously provisioned local model snapshot. CPU inference can use substantially more memory than the raw weight size. Visual, music, and voice learned backends are intentionally not included in v0.1.
