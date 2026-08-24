from __future__ import annotations

import json
import re

from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any


SUPPORTED_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_PATTERN = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)


class ModelManifestError(ValueError):
    """Raised when the packaged model manifest is invalid."""


@dataclass(frozen=True, slots=True)
class ModelFile:
    path: PurePosixPath
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ModelSource:
    repo_id: str
    revision: str
    files: tuple[ModelFile, ...]


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    name: str
    provider: str
    license_name: str
    target_directory: PurePosixPath
    sources: tuple[ModelSource, ...]

    @property
    def files(self) -> tuple[ModelFile, ...]:
        return tuple(
            model_file
            for source in self.sources
            for model_file in source.files
        )

    @property
    def expected_size(self) -> int:
        return sum(
            model_file.size
            for model_file in self.files
        )

    def target_path(self, models_dir: Path) -> Path:
        return models_dir.joinpath(
            *self.target_directory.parts
        )


@dataclass(frozen=True, slots=True)
class ModelManifest:
    schema_version: int
    models: tuple[ModelSpec, ...]

    @property
    def expected_size(self) -> int:
        return sum(
            model.expected_size
            for model in self.models
        )

    def get(self, model_id: str) -> ModelSpec:
        for model in self.models:
            if model.model_id == model_id:
                return model

        raise KeyError(
            f"Unknown model id: {model_id}"
        )


def _require_mapping(
    value: Any,
    *,
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelManifestError(
            f"{field} must be an object."
        )

    return value


def _require_list(
    value: Any,
    *,
    field: str,
) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ModelManifestError(
            f"{field} must be a non-empty array."
        )

    return value


def _require_string(
    value: Any,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelManifestError(
            f"{field} must be a non-empty string."
        )

    return value.strip()


def _relative_path(
    value: Any,
    *,
    field: str,
) -> PurePosixPath:
    raw_path = _require_string(
        value,
        field=field,
    )

    if "\\" in raw_path:
        raise ModelManifestError(
            f"{field} must use forward slashes."
        )

    path = PurePosixPath(raw_path)

    if (
        path.is_absolute()
        or any(
            part in {"", ".", ".."}
            for part in path.parts
        )
    ):
        raise ModelManifestError(
            f"{field} is not a safe relative path: "
            f"{raw_path}"
        )

    return path


def _parse_file(
    payload: Any,
    *,
    field: str,
) -> ModelFile:
    item = _require_mapping(
        payload,
        field=field,
    )

    size = item.get("size")

    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or size <= 0
    ):
        raise ModelManifestError(
            f"{field}.size must be a positive integer."
        )

    sha256 = _require_string(
        item.get("sha256"),
        field=f"{field}.sha256",
    ).lower()

    if not _SHA256_PATTERN.fullmatch(sha256):
        raise ModelManifestError(
            f"{field}.sha256 must be a SHA-256 digest."
        )

    return ModelFile(
        path=_relative_path(
            item.get("path"),
            field=f"{field}.path",
        ),
        size=size,
        sha256=sha256,
    )


def _parse_source(
    payload: Any,
    *,
    field: str,
) -> ModelSource:
    item = _require_mapping(
        payload,
        field=field,
    )

    repo_id = _require_string(
        item.get("repo_id"),
        field=f"{field}.repo_id",
    )

    if not _REPOSITORY_PATTERN.fullmatch(repo_id):
        raise ModelManifestError(
            f"{field}.repo_id is not a valid public "
            "Hugging Face repository id."
        )

    revision = _require_string(
        item.get("revision"),
        field=f"{field}.revision",
    ).lower()

    if not _REVISION_PATTERN.fullmatch(revision):
        raise ModelManifestError(
            f"{field}.revision must be a pinned "
            "40-character commit hash."
        )

    files = tuple(
        _parse_file(
            value,
            field=f"{field}.files[{index}]",
        )
        for index, value in enumerate(
            _require_list(
                item.get("files"),
                field=f"{field}.files",
            )
        )
    )

    return ModelSource(
        repo_id=repo_id,
        revision=revision,
        files=files,
    )


def _parse_model(
    payload: Any,
    *,
    field: str,
) -> ModelSpec:
    item = _require_mapping(
        payload,
        field=field,
    )

    sources = tuple(
        _parse_source(
            value,
            field=f"{field}.sources[{index}]",
        )
        for index, value in enumerate(
            _require_list(
                item.get("sources"),
                field=f"{field}.sources",
            )
        )
    )

    file_paths = [
        model_file.path
        for source in sources
        for model_file in source.files
    ]

    if len(file_paths) != len(set(file_paths)):
        raise ModelManifestError(
            f"{field} contains duplicate destination files."
        )

    return ModelSpec(
        model_id=_require_string(
            item.get("id"),
            field=f"{field}.id",
        ),
        name=_require_string(
            item.get("name"),
            field=f"{field}.name",
        ),
        provider=_require_string(
            item.get("provider"),
            field=f"{field}.provider",
        ),
        license_name=_require_string(
            item.get("license"),
            field=f"{field}.license",
        ),
        target_directory=_relative_path(
            item.get("target_directory"),
            field=f"{field}.target_directory",
        ),
        sources=sources,
    )


def parse_model_manifest(
    payload: Any,
) -> ModelManifest:
    root = _require_mapping(
        payload,
        field="manifest",
    )

    schema_version = root.get(
        "schema_version"
    )

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ModelManifestError(
            "Unsupported model manifest schema version: "
            f"{schema_version!r}"
        )

    models = tuple(
        _parse_model(
            value,
            field=f"models[{index}]",
        )
        for index, value in enumerate(
            _require_list(
                root.get("models"),
                field="models",
            )
        )
    )

    model_ids = [
        model.model_id
        for model in models
    ]

    if len(model_ids) != len(set(model_ids)):
        raise ModelManifestError(
            "Model ids must be unique."
        )

    targets = [
        model.target_directory
        for model in models
    ]

    if len(targets) != len(set(targets)):
        raise ModelManifestError(
            "Model target directories must be unique."
        )

    for index, target in enumerate(targets):
        for other in targets[index + 1 :]:
            if (
                target.parts
                == other.parts[: len(target.parts)]
                or other.parts
                == target.parts[: len(other.parts)]
            ):
                raise ModelManifestError(
                    "Model target directories must not overlap: "
                    f"{target} and {other}"
                )

    return ModelManifest(
        schema_version=schema_version,
        models=models,
    )


def load_model_manifest(
    path: str | Path | None = None,
) -> ModelManifest:
    try:
        if path is None:
            text = (
                resources.files(
                    "bidr_sanitizer.resources"
                )
                .joinpath("model_manifest.json")
                .read_text(encoding="utf-8")
            )
        else:
            text = Path(path).read_text(
                encoding="utf-8"
            )

        payload = json.loads(text)

    except (OSError, json.JSONDecodeError) as exc:
        raise ModelManifestError(
            f"Could not load model manifest: {exc}"
        ) from exc

    return parse_model_manifest(payload)
