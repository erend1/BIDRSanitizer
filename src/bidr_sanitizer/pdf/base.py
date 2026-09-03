from __future__ import annotations

from pathlib import Path
from typing import Protocol

from bidr_sanitizer.pipeline import (
    SanitizationResult,
)
from bidr_sanitizer.redaction import ImageOutputTransform


class ImageSanitizerProvider(Protocol):
    def sanitize(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        margin: int = 5,
        max_redaction_passes: int = 3,
        output_transform: ImageOutputTransform | None = None,
    ) -> SanitizationResult:
        ...
