from __future__ import annotations

from types import SimpleNamespace

import pytest

from bidr_sanitizer.inference_device import (
    resolve_paddle_device,
    resolve_torch_device,
)


class FakeCUDA:
    def __init__(self, *, available: bool, count: int) -> None:
        self._available = available
        self._count = count

    def is_available(self) -> bool:
        return self._available

    def device_count(self) -> int:
        return self._count


def test_auto_device_uses_gpu_when_both_runtimes_expose_it():
    torch_module = SimpleNamespace(
        cuda=FakeCUDA(available=True, count=1),
    )
    paddle_module = SimpleNamespace(
        device=SimpleNamespace(
            is_compiled_with_cuda=lambda: True,
            cuda=FakeCUDA(available=True, count=1),
        )
    )

    assert resolve_torch_device(torch_module, "auto") == "cuda:0"
    assert resolve_paddle_device(paddle_module, "auto") == "gpu:0"


def test_auto_device_falls_back_to_cpu():
    torch_module = SimpleNamespace(
        cuda=FakeCUDA(available=False, count=0),
    )
    paddle_module = SimpleNamespace(
        device=SimpleNamespace(
            is_compiled_with_cuda=lambda: False,
            cuda=FakeCUDA(available=False, count=0),
        )
    )

    assert resolve_torch_device(torch_module, "auto") == "cpu"
    assert resolve_paddle_device(paddle_module, "auto") == "cpu"


def test_explicit_gpu_request_fails_instead_of_silently_using_cpu():
    torch_module = SimpleNamespace(
        cuda=FakeCUDA(available=False, count=0),
    )

    with pytest.raises(RuntimeError, match="CUDA device 0 is unavailable"):
        resolve_torch_device(torch_module, "gpu")


@pytest.mark.parametrize("value", ["", "tpu", "gpu:-1", "gpu:any"])
def test_invalid_device_setting_is_rejected(value):
    with pytest.raises(ValueError, match="BIDR_INFERENCE_DEVICE"):
        resolve_torch_device(SimpleNamespace(), value)
