from __future__ import annotations

import hashlib

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.config import get_models_dir
from bidr_sanitizer.model_manifest import (
    ModelManifest,
    ModelSpec,
    load_model_manifest,
)


class ModelValidationError(RuntimeError):
    """Raised when a required local model is missing or invalid."""


@dataclass(frozen=True, slots=True)
class ModelStatus:
    model_id: str
    name: str
    path: Path
    exists: bool
    valid: bool
    verified_hashes: bool
    problems: tuple[str, ...]

    @property
    def state(self) -> str:
        if self.valid:
            return "valid"

        if not self.exists:
            return "missing"

        return "invalid"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(
            lambda: source.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_model(
    model: ModelSpec,
    target_path: str | Path,
    *,
    verify_hashes: bool,
) -> ModelStatus:
    target = Path(target_path).expanduser().resolve()
    problems: list[str] = []

    if not target.exists():
        problems.append("model directory is missing")

    elif not target.is_dir():
        problems.append("model path is not a directory")

    else:
        for expected_file in model.files:
            file_path = target.joinpath(
                *expected_file.path.parts
            )

            if not file_path.exists():
                problems.append(
                    "missing file: "
                    f"{expected_file.path.as_posix()}"
                )
                continue

            if not file_path.is_file():
                problems.append(
                    "not a regular file: "
                    f"{expected_file.path.as_posix()}"
                )
                continue

            if file_path.stat().st_size != expected_file.size:
                problems.append(
                    "size mismatch: "
                    f"{expected_file.path.as_posix()}"
                )
                continue

            if (
                verify_hashes
                and sha256_file(file_path)
                != expected_file.sha256
            ):
                problems.append(
                    "SHA-256 mismatch: "
                    f"{expected_file.path.as_posix()}"
                )

    return ModelStatus(
        model_id=model.model_id,
        name=model.name,
        path=target,
        exists=target.exists(),
        valid=not problems,
        verified_hashes=verify_hashes,
        problems=tuple(problems),
    )


def check_local_models(
    models_dir: str | Path | None = None,
    *,
    verify_hashes: bool = True,
    manifest: ModelManifest | None = None,
) -> tuple[ModelStatus, ...]:
    root = Path(
        models_dir
        if models_dir is not None
        else get_models_dir()
    ).expanduser().resolve()

    selected_manifest = (
        manifest
        if manifest is not None
        else load_model_manifest()
    )

    return tuple(
        inspect_model(
            model,
            model.target_path(root),
            verify_hashes=verify_hashes,
        )
        for model in selected_manifest.models
    )


def require_local_model(
    model_id: str,
    *,
    models_dir: str | Path | None = None,
    target_path: str | Path | None = None,
    verify_hashes: bool = False,
    manifest: ModelManifest | None = None,
) -> Path:
    selected_manifest = (
        manifest
        if manifest is not None
        else load_model_manifest()
    )
    model = selected_manifest.get(model_id)

    if target_path is None:
        root = Path(
            models_dir
            if models_dir is not None
            else get_models_dir()
        ).expanduser().resolve()
        selected_target = model.target_path(root)
    else:
        selected_target = Path(target_path)

    status = inspect_model(
        model,
        selected_target,
        verify_hashes=verify_hashes,
    )

    if not status.valid:
        details = "\n".join(
            f"  - {problem}"
            for problem in status.problems
        )

        raise ModelValidationError(
            f"Local model '{model.name}' is not ready at:\n"
            f"  {status.path}\n"
            f"{details}\n\n"
            "Run the explicit model installer:\n"
            "  bidr-models install"
        )

    return status.path
