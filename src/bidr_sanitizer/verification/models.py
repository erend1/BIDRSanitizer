from __future__ import annotations

from dataclasses import dataclass

from bidr_sanitizer.models import Detection


@dataclass(frozen=True, slots=True)
class VerificationReport:
    remaining_detections: tuple[Detection, ...]

    @property
    def passed(self) -> bool:
        return len(self.remaining_detections) == 0

    @property
    def remaining_count(self) -> int:
        return len(self.remaining_detections)