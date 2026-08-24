from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.models import (
    TextDetection,
)


@dataclass(frozen=True, slots=True)
class TextVerificationReport:
    remaining_detections: tuple[
        TextDetection,
        ...
    ]

    @property
    def passed(self) -> bool:
        return (
            len(
                self.remaining_detections
            )
            == 0
        )


@dataclass(frozen=True, slots=True)
class TextSanitizationResult:
    output_path: Path
    applied_detections: tuple[
        TextDetection,
        ...
    ]
    verification: TextVerificationReport
    redaction_passes: int

    @property
    def passed(self) -> bool:
        return self.verification.passed