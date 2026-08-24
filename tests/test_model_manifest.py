from __future__ import annotations

import copy
import json

from pathlib import Path

import pytest

from bidr_sanitizer.model_manifest import (
    ModelManifestError,
    load_model_manifest,
    parse_model_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _minimal_payload() -> dict:
    return {
        "schema_version": 1,
        "models": [
            {
                "id": "example",
                "name": "Example",
                "provider": "Example Provider",
                "license": "Apache-2.0",
                "target_directory": "example/model",
                "sources": [
                    {
                        "repo_id": "example/model",
                        "revision": "a" * 40,
                        "files": [
                            {
                                "path": "model.bin",
                                "size": 4,
                                "sha256": "b" * 64,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_packaged_manifest_contains_all_runtime_models():
    manifest = load_model_manifest()

    assert {
        model.model_id
        for model in manifest.models
    } == {
        "paddle-ocr-detection",
        "paddle-ocr-recognition",
        "gliner-pii",
        "yunet-face-detection",
        "signature-detection",
    }

    assert manifest.expected_size == 1_379_612_349


def test_gliner_manifest_includes_local_tokenizer_assets():
    model = load_model_manifest().get(
        "gliner-pii"
    )

    assert {
        model_file.path.as_posix()
        for model_file in model.files
    } >= {
        "gliner_config.json",
        "pytorch_model.bin",
        "config.json",
        "spm.model",
        "tokenizer_config.json",
    }

    assert {
        source.repo_id
        for source in model.sources
    } == {
        "urchade/gliner_multi_pii-v1",
        "microsoft/mdeberta-v3-base",
    }


def test_public_and_packaged_manifests_match():
    public_payload = json.loads(
        (
            PROJECT_ROOT
            / "models"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    packaged_payload = json.loads(
        (
            PROJECT_ROOT
            / "src"
            / "bidr_sanitizer"
            / "resources"
            / "model_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert public_payload == packaged_payload


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.bin",
        "/absolute/model.bin",
        r"windows\\path.bin",
    ],
)
def test_manifest_rejects_unsafe_file_paths(
    unsafe_path,
):
    payload = _minimal_payload()
    payload["models"][0]["sources"][0][
        "files"
    ][0]["path"] = unsafe_path

    with pytest.raises(ModelManifestError):
        parse_model_manifest(payload)


def test_manifest_requires_pinned_revision():
    payload = _minimal_payload()
    payload["models"][0]["sources"][0][
        "revision"
    ] = "main"

    with pytest.raises(
        ModelManifestError,
        match="pinned",
    ):
        parse_model_manifest(payload)


def test_manifest_rejects_overlapping_targets():
    payload = _minimal_payload()
    second = copy.deepcopy(
        payload["models"][0]
    )
    second["id"] = "nested"
    second["target_directory"] = (
        "example/model/nested"
    )
    payload["models"].append(second)

    with pytest.raises(
        ModelManifestError,
        match="must not overlap",
    ):
        parse_model_manifest(payload)
