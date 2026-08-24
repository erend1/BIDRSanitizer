from __future__ import annotations

import hashlib

from pathlib import Path

import pytest

from bidr_sanitizer.model_check import (
    check_local_models,
)
from bidr_sanitizer.model_installer import (
    INSTALLATION_RECEIPT,
    ModelInstallationError,
    ModelInstaller,
    ModelIntegrityError,
    ModelPathError,
    validate_models_dir,
)
from bidr_sanitizer.model_manifest import (
    ModelManifest,
    ModelSource,
    parse_model_manifest,
)


class FakeDownloader:
    def __init__(
        self,
        payloads: dict[tuple[str, str], bytes],
    ) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, str]] = []

    def download(
        self,
        source: ModelSource,
        destination: Path,
    ) -> None:
        self.calls.append(
            (
                source.repo_id,
                source.revision,
            )
        )

        for model_file in source.files:
            path = destination.joinpath(
                *model_file.path.parts
            )
            path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            path.write_bytes(
                self.payloads[
                    (
                        source.repo_id,
                        model_file.path.as_posix(),
                    )
                ]
            )


def _file_payload(
    path: str,
    content: bytes,
) -> dict:
    return {
        "path": path,
        "size": len(content),
        "sha256": hashlib.sha256(
            content
        ).hexdigest(),
    }


def _tiny_manifest() -> tuple[
    ModelManifest,
    dict[tuple[str, str], bytes],
]:
    weights = b"pinned weights"
    tokenizer = b"pinned tokenizer"
    payloads = {
        ("tests/model", "weights.bin"): weights,
        ("tests/tokenizer", "tokenizer.json"): tokenizer,
    }
    manifest = parse_model_manifest(
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
                            "repo_id": "tests/model",
                            "revision": "1" * 40,
                            "files": [
                                _file_payload(
                                    "weights.bin",
                                    weights,
                                )
                            ],
                        },
                        {
                            "repo_id": "tests/tokenizer",
                            "revision": "2" * 40,
                            "files": [
                                _file_payload(
                                    "tokenizer.json",
                                    tokenizer,
                                )
                            ],
                        },
                    ],
                }
            ],
        }
    )
    return manifest, payloads


def _installer(
    models_dir: Path,
    manifest: ModelManifest,
    downloader: FakeDownloader,
) -> ModelInstaller:
    return ModelInstaller(
        models_dir=models_dir,
        manifest=manifest,
        downloader=downloader,
        platform_name="posix",
        source_checkout_root=(
            models_dir.parent
            / "unrelated-source-checkout"
        ),
    )


def test_installer_stages_verifies_and_promotes(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    downloader = FakeDownloader(payloads)
    models_dir = tmp_path / "models"
    installer = _installer(
        models_dir,
        manifest,
        downloader,
    )

    report = installer.install()

    target = models_dir / "tiny" / "model"
    assert (target / "weights.bin").read_bytes() == (
        b"pinned weights"
    )
    assert (target / "tokenizer.json").read_bytes() == (
        b"pinned tokenizer"
    )
    assert report.results[0].action == "installed"
    assert len(downloader.calls) == 2
    assert (
        models_dir / INSTALLATION_RECEIPT
    ).is_file()

    status = check_local_models(
        models_dir,
        manifest=manifest,
    )[0]
    assert status.valid


def test_installer_is_idempotent(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    downloader = FakeDownloader(payloads)
    installer = _installer(
        tmp_path / "models",
        manifest,
        downloader,
    )
    installer.install()
    call_count = len(downloader.calls)

    report = installer.install()

    assert report.results[0].action == (
        "already-installed"
    )
    assert len(downloader.calls) == call_count


def test_invalid_existing_model_requires_repair(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    downloader = FakeDownloader(payloads)
    models_dir = tmp_path / "models"
    installer = _installer(
        models_dir,
        manifest,
        downloader,
    )
    installer.install()
    target_file = (
        models_dir
        / "tiny"
        / "model"
        / "weights.bin"
    )
    target_file.write_bytes(
        b"x" * len(b"pinned weights")
    )
    call_count = len(downloader.calls)

    with pytest.raises(
        ModelInstallationError,
        match="--repair",
    ):
        installer.install()

    assert len(downloader.calls) == call_count
    assert target_file.read_bytes() != (
        b"pinned weights"
    )

    report = installer.install(repair=True)

    assert report.results[0].action == "repaired"
    assert target_file.read_bytes() == b"pinned weights"


def test_hash_failure_never_reaches_final_model_path(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    corrupt_payloads = {
        key: b"x" * len(value)
        for key, value in payloads.items()
    }
    downloader = FakeDownloader(
        corrupt_payloads
    )
    models_dir = tmp_path / "models"
    installer = _installer(
        models_dir,
        manifest,
        downloader,
    )

    with pytest.raises(
        ModelIntegrityError,
        match="integrity verification",
    ):
        installer.install()

    assert not (
        models_dir / "tiny" / "model"
    ).exists()
    assert not (
        models_dir
        / ".staging"
        / "tiny-model"
        / "weights.bin"
    ).exists()


def test_failed_repair_preserves_existing_model(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    models_dir = tmp_path / "models"
    target = models_dir / "tiny" / "model"
    target.mkdir(parents=True)
    old_content = b"existing custom bytes"
    (target / "weights.bin").write_bytes(
        old_content
    )

    corrupt_payloads = {
        key: b"x" * len(value)
        for key, value in payloads.items()
    }
    installer = _installer(
        models_dir,
        manifest,
        FakeDownloader(corrupt_payloads),
    )

    with pytest.raises(ModelIntegrityError):
        installer.install(repair=True)

    assert (target / "weights.bin").read_bytes() == (
        old_content
    )


def test_installer_refuses_concurrent_lock(
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    models_dir = tmp_path / "models"
    lock_path = (
        models_dir.parent
        / f".{models_dir.name}.install.lock"
    )
    lock_path.write_text(
        "existing lock",
        encoding="utf-8",
    )
    installer = _installer(
        models_dir,
        manifest,
        FakeDownloader(payloads),
    )

    with pytest.raises(
        ModelInstallationError,
        match="appears to be running",
    ):
        installer.install()


def test_windows_installer_rejects_non_ascii_path(
    tmp_path,
):
    path = tmp_path / "RUMELİ" / "models"

    with pytest.raises(
        ModelPathError,
        match="non-ASCII",
    ):
        validate_models_dir(
            path,
            platform_name="nt",
            source_checkout_root=(
                tmp_path / "unrelated"
            ),
        )


def test_installer_rejects_source_checkout_destination(
    tmp_path,
):
    checkout = tmp_path / "checkout"
    destination = checkout / "models" / "weights"

    with pytest.raises(
        ModelPathError,
        match="source repository",
    ):
        validate_models_dir(
            destination,
            platform_name="posix",
            source_checkout_root=checkout,
        )


def test_installer_rejects_symlinked_stage_file(
    monkeypatch,
    tmp_path,
):
    manifest, payloads = _tiny_manifest()
    downloader = FakeDownloader(payloads)
    models_dir = tmp_path / "models"
    installer = _installer(
        models_dir,
        manifest,
        downloader,
    )
    real_is_symlink = Path.is_symlink

    def fake_is_symlink(path):
        if path.name == "weights.bin":
            return True

        return real_is_symlink(path)

    monkeypatch.setattr(
        Path,
        "is_symlink",
        fake_is_symlink,
    )

    with pytest.raises(
        ModelPathError,
        match="Staged model files",
    ):
        installer.install()

    assert downloader.calls == []
