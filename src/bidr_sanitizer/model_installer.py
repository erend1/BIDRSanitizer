from __future__ import annotations

import json
import os
import shutil
import uuid

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from bidr_sanitizer.config import (
    get_models_dir,
    is_ascii_path,
)
from bidr_sanitizer.model_check import (
    ModelStatus,
    check_local_models,
    inspect_model,
    sha256_file,
)
from bidr_sanitizer.model_manifest import (
    ModelManifest,
    ModelSource,
    ModelSpec,
    load_model_manifest,
)


INSTALLATION_RECEIPT = ".bidr-models.json"
STAGING_DIRECTORY = ".staging"
BACKUP_DIRECTORY = ".backup"


class ModelInstallationError(RuntimeError):
    """Base error for explicit model installation failures."""


class ModelPathError(ModelInstallationError):
    """Raised when a model installation path is unsafe."""


class ModelIntegrityError(ModelInstallationError):
    """Raised when downloaded model files fail verification."""


class DownloadBackend(Protocol):
    def download(
        self,
        source: ModelSource,
        destination: Path,
    ) -> None:
        """Download one pinned source into destination."""


class HuggingFaceDownloader:
    """Download only manifest-selected files from pinned Hub revisions."""

    def download(
        self,
        source: ModelSource,
        destination: Path,
    ) -> None:
        try:
            from huggingface_hub import snapshot_download
        except ModuleNotFoundError as exc:
            raise ModelInstallationError(
                "Model installation support is not installed.\n\n"
                "Install it with:\n"
                '  python -m pip install "bidr-sanitizer[model-install]"'
            ) from exc

        os.environ.setdefault(
            "HF_HUB_DISABLE_TELEMETRY",
            "1",
        )

        try:
            snapshot_download(
                repo_id=source.repo_id,
                revision=source.revision,
                local_dir=str(destination),
                allow_patterns=[
                    model_file.path.as_posix()
                    for model_file in source.files
                ],
            )
        except Exception as exc:
            raise ModelInstallationError(
                "Could not download pinned model source "
                f"{source.repo_id}@{source.revision}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class ModelInstallResult:
    model_id: str
    name: str
    path: Path
    action: str


@dataclass(frozen=True, slots=True)
class InstallationReport:
    models_dir: Path
    results: tuple[ModelInstallResult, ...]


def _is_within(
    candidate: Path,
    parent: Path,
) -> bool:
    return (
        candidate == parent
        or parent in candidate.parents
    )


def _source_checkout_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (
            (parent / "pyproject.toml").is_file()
            and (parent / "models" / "manifest.json").is_file()
        ):
            return parent

    return None


def validate_models_dir(
    models_dir: str | Path,
    *,
    platform_name: str | None = None,
    source_checkout_root: Path | None = None,
) -> Path:
    selected_platform = (
        os.name
        if platform_name is None
        else platform_name
    )
    resolved = Path(
        models_dir
    ).expanduser().resolve()

    if resolved == Path(resolved.anchor):
        raise ModelPathError(
            "The filesystem root cannot be used as the model directory."
        )

    if resolved.exists() and not resolved.is_dir():
        raise ModelPathError(
            "The model destination is not a directory: "
            f"{resolved}"
        )

    package_directory = Path(
        __file__
    ).resolve().parent

    if _is_within(
        resolved,
        package_directory,
    ):
        raise ModelPathError(
            "Model weights must not be installed inside the "
            "BIDR Sanitizer Python package."
        )

    checkout_root = (
        source_checkout_root
        if source_checkout_root is not None
        else _source_checkout_root()
    )

    if (
        checkout_root is not None
        and _is_within(
            resolved,
            checkout_root.resolve(),
        )
    ):
        raise ModelPathError(
            "Model weights must not be installed inside the "
            "BIDR Sanitizer source repository."
        )

    if (
        selected_platform == "nt"
        and not is_ascii_path(resolved)
    ):
        raise ModelPathError(
            "The resolved Windows model path contains non-ASCII "
            "characters that may fail in Paddle's native runtime:\n"
            f"  {resolved}\n\n"
            "Choose an ASCII-safe path, for example:\n"
            "  bidr-models install --models-dir C:\\BIDRModels"
        )

    return resolved


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path

    while not candidate.exists():
        if candidate.parent == candidate:
            break
        candidate = candidate.parent

    return candidate


def _assert_target_within_root(
    target: Path,
    root: Path,
) -> None:
    resolved_target = target.resolve()
    resolved_root = root.resolve()

    if not _is_within(
        resolved_target,
        resolved_root,
    ):
        raise ModelPathError(
            "A model target resolves outside the configured "
            f"model directory: {target}"
        )


def _assert_no_symlink_components(
    model: ModelSpec,
    stage_path: Path,
) -> None:
    for expected_file in model.files:
        candidate = stage_path

        for part in expected_file.path.parts:
            candidate = candidate / part

            if candidate.is_symlink():
                raise ModelPathError(
                    "Staged model files may not be symbolic links: "
                    f"{candidate}"
                )

        _assert_target_within_root(
            candidate,
            stage_path,
        )


def _required_download_bytes(
    statuses: tuple[ModelStatus, ...],
    manifest: ModelManifest,
) -> int:
    status_by_id = {
        status.model_id: status
        for status in statuses
    }

    return sum(
        model.expected_size
        for model in manifest.models
        if not status_by_id[model.model_id].valid
    )


def _check_disk_space(
    models_dir: Path,
    required_bytes: int,
) -> None:
    if required_bytes <= 0:
        return

    disk_root = _nearest_existing_parent(
        models_dir
    )
    free_bytes = shutil.disk_usage(
        disk_root
    ).free
    reserve = max(
        64 * 1024 * 1024,
        required_bytes // 20,
    )

    if free_bytes < required_bytes + reserve:
        raise ModelInstallationError(
            "Insufficient free disk space for staged model "
            "installation.\n"
            f"Required (including reserve): "
            f"{required_bytes + reserve:,} bytes\n"
            f"Available: {free_bytes:,} bytes"
        )


@contextmanager
def _installation_lock(
    models_dir: Path,
) -> Iterator[None]:
    models_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    lock_path = (
        models_dir.parent
        / f".{models_dir.name}.install.lock"
    )

    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError as exc:
        raise ModelInstallationError(
            "Another model installation appears to be running.\n"
            f"Lock file: {lock_path}\n"
            "If no installer is running, remove this stale lock "
            "file and retry."
        ) from exc

    try:
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        ).encode("utf-8")
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)

    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _safe_remove(
    path: Path,
    *,
    allowed_parent: Path,
) -> None:
    absolute_path = path.absolute()
    absolute_parent = allowed_parent.absolute()

    if not _is_within(
        absolute_path,
        absolute_parent,
    ):
        raise ModelPathError(
            f"Refusing unsafe cleanup target: {path}"
        )

    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _remove_invalid_stage_files(
    model: ModelSpec,
    stage_path: Path,
) -> None:
    for expected_file in model.files:
        file_path = stage_path.joinpath(
            *expected_file.path.parts
        )

        if not file_path.is_file():
            continue

        if (
            file_path.stat().st_size != expected_file.size
            or sha256_file(file_path)
            != expected_file.sha256
        ):
            file_path.unlink()


def _format_problems(
    status: ModelStatus,
) -> str:
    return "\n".join(
        f"  - {problem}"
        for problem in status.problems
    )


class ModelInstaller:
    def __init__(
        self,
        *,
        models_dir: str | Path | None = None,
        manifest: ModelManifest | None = None,
        downloader: DownloadBackend | None = None,
        platform_name: str | None = None,
        source_checkout_root: Path | None = None,
    ) -> None:
        self._manifest = (
            manifest
            if manifest is not None
            else load_model_manifest()
        )
        self._models_dir = validate_models_dir(
            models_dir
            if models_dir is not None
            else get_models_dir(),
            platform_name=platform_name,
            source_checkout_root=source_checkout_root,
        )
        self._downloader = (
            downloader
            if downloader is not None
            else HuggingFaceDownloader()
        )

    @property
    def models_dir(self) -> Path:
        return self._models_dir

    def _statuses(self) -> tuple[ModelStatus, ...]:
        return check_local_models(
            self._models_dir,
            verify_hashes=True,
            manifest=self._manifest,
        )

    def _validate_targets(self) -> None:
        for model in self._manifest.models:
            target = model.target_path(
                self._models_dir
            )

            if target.is_symlink():
                raise ModelPathError(
                    "Model target directories may not be symbolic "
                    f"links during installation: {target}"
                )

            _assert_target_within_root(
                target,
                self._models_dir,
            )

    def _download_to_stage(
        self,
        model: ModelSpec,
    ) -> Path:
        stage_root = (
            self._models_dir
            / STAGING_DIRECTORY
        )
        stage_path = (
            stage_root
            / model.model_id
        )

        for work_path in (
            stage_root,
            stage_path,
        ):
            if work_path.is_symlink():
                raise ModelPathError(
                    "Installer staging directories may not be "
                    f"symbolic links: {work_path}"
                )

            _assert_target_within_root(
                work_path,
                self._models_dir,
            )

        stage_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        _assert_no_symlink_components(
            model,
            stage_path,
        )

        for source in model.sources:
            self._downloader.download(
                source,
                stage_path,
            )

        _assert_no_symlink_components(
            model,
            stage_path,
        )

        status = inspect_model(
            model,
            stage_path,
            verify_hashes=True,
        )

        if not status.valid:
            _remove_invalid_stage_files(
                model,
                stage_path,
            )
            raise ModelIntegrityError(
                f"Downloaded model '{model.name}' failed "
                "integrity verification:\n"
                f"{_format_problems(status)}"
            )

        cache_path = stage_path / ".cache"
        if cache_path.exists():
            _safe_remove(
                cache_path,
                allowed_parent=stage_path,
            )

        return stage_path

    def _promote(
        self,
        model: ModelSpec,
        stage_path: Path,
        *,
        replacing: bool,
    ) -> None:
        target = model.target_path(
            self._models_dir
        )
        _assert_target_within_root(
            target,
            self._models_dir,
        )
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        backup_path: Path | None = None

        if replacing:
            backup_root = (
                self._models_dir
                / BACKUP_DIRECTORY
            )

            if backup_root.is_symlink():
                raise ModelPathError(
                    "Installer backup directory may not be a "
                    f"symbolic link: {backup_root}"
                )

            _assert_target_within_root(
                backup_root,
                self._models_dir,
            )
            backup_root.mkdir(
                parents=True,
                exist_ok=True,
            )
            backup_path = (
                backup_root
                / (
                    model.model_id
                    + "-"
                    + uuid.uuid4().hex
                )
            )
            _assert_target_within_root(
                backup_path,
                backup_root,
            )
            target.rename(backup_path)

        try:
            stage_path.rename(target)

            verified = inspect_model(
                model,
                target,
                verify_hashes=True,
            )

            if not verified.valid:
                raise ModelIntegrityError(
                    "Promoted model failed final verification:\n"
                    f"{_format_problems(verified)}"
                )

        except Exception:
            if target.exists():
                _safe_remove(
                    target,
                    allowed_parent=self._models_dir,
                )

            if backup_path is not None:
                backup_path.rename(target)

            raise

        if backup_path is not None:
            _safe_remove(
                backup_path,
                allowed_parent=(
                    self._models_dir
                    / BACKUP_DIRECTORY
                ),
            )

    def _write_receipt(self) -> None:
        receipt_path = (
            self._models_dir
            / INSTALLATION_RECEIPT
        )
        temporary_path = (
            self._models_dir
            / (
                INSTALLATION_RECEIPT
                + ".tmp-"
                + uuid.uuid4().hex
            )
        )
        payload = {
            "schema_version": self._manifest.schema_version,
            "installed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "models": [
                {
                    "id": model.model_id,
                    "target_directory": (
                        model.target_directory.as_posix()
                    ),
                    "sources": [
                        {
                            "repo_id": source.repo_id,
                            "revision": source.revision,
                        }
                        for source in model.sources
                    ],
                }
                for model in self._manifest.models
            ],
        }

        temporary_path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(
            temporary_path,
            receipt_path,
        )

    def install(
        self,
        *,
        repair: bool = False,
    ) -> InstallationReport:
        initial_statuses = self._statuses()

        invalid_existing = [
            status
            for status in initial_statuses
            if status.exists and not status.valid
        ]

        if invalid_existing and not repair:
            details = "\n\n".join(
                f"{status.name} ({status.path}):\n"
                f"{_format_problems(status)}"
                for status in invalid_existing
            )
            raise ModelInstallationError(
                "Existing model installations are incomplete or "
                "invalid. No files were changed.\n\n"
                f"{details}\n\n"
                "Run 'bidr-models install --repair' to replace "
                "them transactionally."
            )

        _check_disk_space(
            self._models_dir,
            _required_download_bytes(
                initial_statuses,
                self._manifest,
            ),
        )

        results: list[ModelInstallResult] = []

        with _installation_lock(
            self._models_dir
        ):
            self._models_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            self._validate_targets()

            current_statuses = {
                status.model_id: status
                for status in self._statuses()
            }

            for model in self._manifest.models:
                status = current_statuses[
                    model.model_id
                ]
                target = model.target_path(
                    self._models_dir
                )

                if status.valid:
                    results.append(
                        ModelInstallResult(
                            model_id=model.model_id,
                            name=model.name,
                            path=target,
                            action="already-installed",
                        )
                    )
                    continue

                replacing = status.exists

                if replacing and not repair:
                    raise ModelInstallationError(
                        "A model became invalid while installation "
                        "was starting. Retry with --repair."
                    )

                stage_path = self._download_to_stage(
                    model
                )
                self._promote(
                    model,
                    stage_path,
                    replacing=replacing,
                )
                results.append(
                    ModelInstallResult(
                        model_id=model.model_id,
                        name=model.name,
                        path=target,
                        action=(
                            "repaired"
                            if replacing
                            else "installed"
                        ),
                    )
                )

            final_statuses = self._statuses()
            failures = [
                status
                for status in final_statuses
                if not status.valid
            ]

            if failures:
                raise ModelIntegrityError(
                    "Installation completed with invalid model "
                    "state; no success receipt was written."
                )

            self._write_receipt()

        return InstallationReport(
            models_dir=self._models_dir,
            results=tuple(results),
        )
