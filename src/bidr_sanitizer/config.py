from __future__ import annotations

import os

from pathlib import Path


APP_NAME = "BIDRSanitizer"

MODELS_ENV_VAR = "BIDR_MODELS_DIR"

PADDLE_CACHE_ENV_VAR = (
    "PADDLE_PDX_CACHE_HOME"
)


def _normalize_path(
    value: str | Path,
) -> Path:
    return (
        Path(value)
        .expanduser()
        .resolve()
    )


def _default_app_data_dir() -> Path:
    if os.name == "nt":
        local_app_data = (
            os.environ.get(
                "LOCALAPPDATA"
            )
        )

        if not local_app_data:
            raise RuntimeError(
                "LOCALAPPDATA is not defined. "
                "BIDR Sanitizer cannot determine "
                "its default application data "
                "directory."
            )

        return _normalize_path(
            Path(local_app_data)
            / APP_NAME
        )

    xdg_data_home = (
        os.environ.get(
            "XDG_DATA_HOME"
        )
    )

    if xdg_data_home:
        return _normalize_path(
            Path(xdg_data_home)
            / "bidr-sanitizer"
        )

    return _normalize_path(
        Path.home()
        / ".local"
        / "share"
        / "bidr-sanitizer"
    )


def get_models_dir() -> Path:
    explicit = (
        os.environ.get(
            MODELS_ENV_VAR
        )
    )

    if explicit:
        return _normalize_path(
            explicit
        )

    return (
        _default_app_data_dir()
        / "models"
    )


def get_paddle_cache_dir() -> Path:
    explicit = (
        os.environ.get(
            PADDLE_CACHE_ENV_VAR
        )
    )

    if explicit:
        return _normalize_path(
            explicit
        )

    return (
        _default_app_data_dir()
        / "paddlex_cache"
    )


APP_DATA_DIR = (
    _default_app_data_dir()
)

MODELS_DIR = (
    get_models_dir()
)

PADDLE_CACHE_DIR = (
    get_paddle_cache_dir()
)


PADDLE_DETECTION_MODEL_DIR = (
    MODELS_DIR
    / "paddleocr"
    / "PP-OCRv5_server_det"
)

PADDLE_RECOGNITION_MODEL_DIR = (
    MODELS_DIR
    / "paddleocr"
    / "latin_PP-OCRv5_mobile_rec"
)

GLINER_MODEL_DIR = (
    MODELS_DIR
    / "gliner"
    / "gliner_multi_pii_v1"
)

YUNET_MODEL_PATH = (
    MODELS_DIR
    / "yunet"
    / "face_detection_yunet_2023mar.onnx"
)

SIGNATURE_MODEL_DIR = (
    MODELS_DIR
    / "signature"
    / "yolos-small-signature-detection"
)


def configure_paddle_environment() -> None:
    os.environ.setdefault(
        PADDLE_CACHE_ENV_VAR,
        str(PADDLE_CACHE_DIR),
    )


def is_ascii_path(
    path: str | Path,
) -> bool:
    try:
        str(path).encode(
            "ascii"
        )
    except UnicodeEncodeError:
        return False

    return True