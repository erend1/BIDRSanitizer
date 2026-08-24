from __future__ import annotations

from types import SimpleNamespace

import pytest

from bidr_sanitizer import model_cli


def test_model_help_does_not_require_downloader(
    capsys,
):
    with pytest.raises(SystemExit) as exc_info:
        model_cli.main(["--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr()
    assert "bidr-models" in output.out
    assert "install" in output.out
    assert "check" in output.out


def test_model_check_reports_all_missing_models(
    tmp_path,
    capsys,
):
    result = model_cli.main(
        [
            "check",
            "--models-dir",
            str(tmp_path / "models"),
            "--quick",
        ]
    )

    assert result == 1
    output = capsys.readouterr()
    assert "MODEL CHECK FAILED" in output.out
    assert "PP-OCRv5_server_det" in output.out
    assert "gliner_multi_pii-v1" in output.out
    assert "face_detection_yunet_2023mar.onnx" in output.out
    assert "yolos-small-signature-detection" in output.out


def test_model_install_cli_uses_explicit_installer(
    monkeypatch,
    tmp_path,
    capsys,
):
    selected_dir = tmp_path / "models"

    class FakeManifest:
        expected_size = 123

    class FakeInstaller:
        def __init__(
            self,
            *,
            models_dir,
            manifest,
        ):
            assert models_dir == selected_dir.resolve()
            assert isinstance(manifest, FakeManifest)

        def install(self, *, repair):
            assert repair
            return SimpleNamespace(
                results=(
                    SimpleNamespace(
                        action="installed",
                        name="Tiny Model",
                        path=selected_dir / "tiny",
                    ),
                )
            )

    monkeypatch.setattr(
        model_cli,
        "load_model_manifest",
        FakeManifest,
    )
    monkeypatch.setattr(
        model_cli,
        "ModelInstaller",
        FakeInstaller,
    )

    result = model_cli.main(
        [
            "install",
            "--models-dir",
            str(selected_dir),
            "--repair",
        ]
    )

    assert result == 0
    output = capsys.readouterr()
    assert "MODEL INSTALLATION PASSED" in output.out
    assert "Normal sanitization remains offline" in output.out
