from __future__ import annotations

import json
import os
import sys

from types import ModuleType

import pytest

from bidr_sanitizer.recognizers.semantic.gliner_adapter import (
    GLiNERPIIRecognizer,
    _load_self_contained_gliner,
)


def _write_self_contained_model(model_path):
    model_path.mkdir()
    (model_path / "gliner_config.json").write_text(
        json.dumps(
            {
                "model_name": "remote/backbone",
                "hidden_size": 512,
            }
        ),
        encoding="utf-8",
    )
    (model_path / "config.json").write_text(
        json.dumps(
            {
                "model_type": "deberta-v2",
                "hidden_size": 768,
            }
        ),
        encoding="utf-8",
    )
    (model_path / "spm.model").write_bytes(b"tokenizer")
    (model_path / "tokenizer_config.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (model_path / "pytorch_model.bin").write_bytes(
        b"weights"
    )


def test_self_contained_gliner_uses_only_local_config(
    monkeypatch,
    tmp_path,
):
    model_path = tmp_path / "gliner"
    _write_self_contained_model(model_path)
    calls = {}

    class FakeTorchModel:
        def load_state_dict(self, state_dict, *, strict):
            calls["state_dict"] = state_dict
            calls["strict"] = strict

        def to(self, device):
            calls["device"] = device

    class FakeLoadedModel:
        def __init__(self):
            self.model = FakeTorchModel()
            self.eval_calls = 0

        def eval(self):
            self.eval_calls += 1

    loaded_model = FakeLoadedModel()

    class FakeGLiNER:
        @classmethod
        def from_config(cls, config, **kwargs):
            calls["config"] = config
            calls["config_kwargs"] = kwargs
            return loaded_model

    gliner_module = ModuleType("gliner")
    gliner_module.GLiNER = FakeGLiNER
    monkeypatch.setitem(
        sys.modules,
        "gliner",
        gliner_module,
    )

    torch_module = ModuleType("torch")

    def fake_load(path, **kwargs):
        calls["weight_path"] = path
        calls["load_kwargs"] = kwargs
        return {"weight": "local"}

    torch_module.load = fake_load
    monkeypatch.setitem(
        sys.modules,
        "torch",
        torch_module,
    )

    recognizer = GLiNERPIIRecognizer(
        model_path=model_path,
    )

    assert recognizer._model is loaded_model
    assert calls["config"]["model_name"] == str(
        model_path.resolve()
    )
    assert calls["config"]["encoder_config"] == {
        "model_type": "deberta-v2",
        "hidden_size": 768,
    }
    assert calls["config_kwargs"] == {
        "backbone_from_pretrained": False,
        "map_location": "cpu",
    }
    assert calls["weight_path"] == (
        model_path.resolve()
        / "pytorch_model.bin"
    )
    assert calls["load_kwargs"] == {
        "map_location": "cpu",
        "weights_only": True,
    }
    assert calls["state_dict"] == {
        "weight": "local"
    }
    assert calls["strict"] is False
    assert calls["device"] == "cpu"
    assert loaded_model.eval_calls == 2
    assert sys.modules["gliner"] is gliner_module
    assert sys.modules["torch"] is torch_module
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_custom_legacy_gliner_path_uses_offline_fallback(
    monkeypatch,
    tmp_path,
):
    model_path = tmp_path / "legacy-gliner"
    model_path.mkdir()
    calls = {}

    class FakeLoadedModel:
        def eval(self):
            calls["eval"] = True

    class FakeGLiNER:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["path"] = path
            calls["kwargs"] = kwargs
            return FakeLoadedModel()

    gliner_module = ModuleType("gliner")
    gliner_module.GLiNER = FakeGLiNER
    monkeypatch.setitem(
        sys.modules,
        "gliner",
        gliner_module,
    )

    GLiNERPIIRecognizer(
        model_path=model_path,
    )

    assert calls["path"] == str(model_path.resolve())
    assert calls["kwargs"] == {
        "local_files_only": True,
    }
    assert calls["eval"] is True


def test_self_contained_gliner_rejects_non_object_config(
    tmp_path,
):
    model_path = tmp_path / "gliner"
    model_path.mkdir()
    (model_path / "gliner_config.json").write_text(
        "[]",
        encoding="utf-8",
    )
    (model_path / "config.json").write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="configuration must be a JSON object",
    ):
        _load_self_contained_gliner(
            object(),
            model_path,
        )
