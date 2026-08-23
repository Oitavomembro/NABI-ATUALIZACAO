from __future__ import annotations

from .model_artifact import ModelArtifactManifest


QWEN3_1_7B_Q4_K_M_CANDIDATE = ModelArtifactManifest(
    model_id="ggml-org/Qwen3-1.7B-GGUF:Q4_K_M",
    filename="Qwen3-1.7B-Q4_K_M.gguf",
    quantization="Q4_K_M",
    source_url=(
        "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/"
        "daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf"
    ),
    source_revision="daeb8e2d528a760970442092f6bf1e55c3b659eb",
    license_id="Apache-2.0",
    sha256="d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5",
    size_bytes=1_282_439_264,
)
