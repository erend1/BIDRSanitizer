from __future__ import annotations

import os
from typing import Any


INFERENCE_DEVICE_ENV_VAR = "BIDR_INFERENCE_DEVICE"


def _requested_device(value: str | None = None) -> tuple[str, int]:
    raw = value if value is not None else os.environ.get(
        INFERENCE_DEVICE_ENV_VAR,
        "auto",
    )
    normalized = raw.strip().lower()

    if normalized in {"auto", "cpu"}:
        return normalized, 0

    prefix, separator, index_text = normalized.partition(":")
    if prefix not in {"cuda", "gpu"}:
        raise ValueError(
            f"{INFERENCE_DEVICE_ENV_VAR} must be auto, cpu, gpu, gpu:N, "
            "cuda, or cuda:N."
        )

    if not separator:
        return "gpu", 0

    if not index_text.isdigit():
        raise ValueError(
            f"{INFERENCE_DEVICE_ENV_VAR} GPU index must be a non-negative integer."
        )

    return "gpu", int(index_text)


def resolve_torch_device(torch_module: Any, value: str | None = None) -> str:
    requested, index = _requested_device(value)
    if requested == "cpu":
        return "cpu"

    cuda = getattr(torch_module, "cuda", None)
    available = bool(cuda is not None and cuda.is_available())
    count = int(cuda.device_count()) if available else 0

    if available and index < count:
        return f"cuda:{index}"

    if requested == "auto":
        return "cpu"

    raise RuntimeError(
        f"GPU inference was requested, but CUDA device {index} is unavailable "
        "to PyTorch."
    )


def resolve_paddle_device(paddle_module: Any, value: str | None = None) -> str:
    requested, index = _requested_device(value)
    if requested == "cpu":
        return "cpu"

    paddle_device = getattr(paddle_module, "device", None)
    compiled = bool(
        paddle_device is not None
        and paddle_device.is_compiled_with_cuda()
    )
    cuda = getattr(paddle_device, "cuda", None)
    count = int(cuda.device_count()) if compiled and cuda is not None else 0

    if compiled and index < count:
        return f"gpu:{index}"

    if requested == "auto":
        return "cpu"

    raise RuntimeError(
        f"GPU inference was requested, but CUDA device {index} is unavailable "
        "to PaddlePaddle."
    )
