from __future__ import annotations

import hashlib

from pathlib import Path

import pytest

from bidr_sanitizer.model_check import (
    ModelValidationError,
    check_local_models,
    require_local_model,
)
from bidr_sanitizer.model_manifest import (
    ModelManifest,
    parse_model_manifest,
)


def _manifest_for(
    content: bytes,
) -> ModelManifest:
    return parse_model_manifest(
        {
            "schema_version": 1,
            "models": [
                {
                    "id": "tiny-model",
                    "name": "Tiny Model",
                    "provider": "Tests",
                    "license": "Apache-2.0",
                    "target_directory": "tiny/model",
                    "sources": [
                        {
                            "repo_id": "tests/tiny-model",
                            "revision": "1" * 40,
                            "files": [
                                {
                                    "path": "weights.bin",
                                    "size": len(content),
                                    "sha256": hashlib.sha256(
                                        content
                                    ).hexdigest(),
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def _write_model(
    root: Path,
    content: bytes,
) -> Path:
    target = root / "tiny" / "model"
    target.mkdir(parents=True)
    (target / "weights.bin").write_bytes(
        content
    )
    return target


def test_full_model_check_verifies_hashes(
    tmp_path,
):
    content = b"known model bytes"
    manifest = _manifest_for(content)
    _write_model(tmp_path, content)

    status = check_local_models(
        tmp_path,
        verify_hashes=True,
        manifest=manifest,
    )[0]

    assert status.valid
    assert status.state == "valid"
    assert status.verified_hashes
    assert status.problems == ()


def test_model_check_detects_same_size_corruption(
    tmp_path,
):
    content = b"known model bytes"
    manifest = _manifest_for(content)
    target = _write_model(
        tmp_path,
        b"x" * len(content),
    )

    quick_status = check_local_models(
        tmp_path,
        verify_hashes=False,
        manifest=manifest,
    )[0]
    full_status = check_local_models(
        tmp_path,
        verify_hashes=True,
        manifest=manifest,
    )[0]

    assert quick_status.valid
    assert not full_status.valid
    assert full_status.state == "invalid"
    assert full_status.problems == (
        "SHA-256 mismatch: weights.bin",
    )
    assert target.exists()


def test_model_check_reports_missing_required_file(
    tmp_path,
):
    manifest = _manifest_for(b"model")
    target = tmp_path / "tiny" / "model"
    target.mkdir(parents=True)

    status = check_local_models(
        tmp_path,
        manifest=manifest,
    )[0]

    assert status.exists
    assert not status.valid
    assert status.problems == (
        "missing file: weights.bin",
    )


def test_require_local_model_has_actionable_error(
    tmp_path,
):
    manifest = _manifest_for(b"model")

    with pytest.raises(
        ModelValidationError,
        match="bidr-models install",
    ):
        require_local_model(
            "tiny-model",
            models_dir=tmp_path,
            manifest=manifest,
        )
