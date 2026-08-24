from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.config import (
    GLINER_MODEL_DIR,
    PADDLE_DETECTION_MODEL_DIR,
    PADDLE_RECOGNITION_MODEL_DIR,
    YUNET_MODEL_PATH,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ModelStatus:
    name: str
    path: Path
    exists: bool


def check_local_models() -> tuple[
    ModelStatus,
    ...
]:
    return (
        ModelStatus(
            name="PaddleOCR detection",
            path=PADDLE_DETECTION_MODEL_DIR,
            exists=(
                PADDLE_DETECTION_MODEL_DIR
                .exists()
            ),
        ),
        ModelStatus(
            name="PaddleOCR recognition",
            path=PADDLE_RECOGNITION_MODEL_DIR,
            exists=(
                PADDLE_RECOGNITION_MODEL_DIR
                .exists()
            ),
        ),
        ModelStatus(
            name="GLiNER PII",
            path=GLINER_MODEL_DIR,
            exists=(
                GLINER_MODEL_DIR.exists()
            ),
        ),
        ModelStatus(
            name="YuNet face",
            path=YUNET_MODEL_PATH,
            exists=(
                YUNET_MODEL_PATH.exists()
            ),
        ),
    )