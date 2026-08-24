from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from bidr_sanitizer.models import (
    Detection,
    DetectionType,
)


def count_detections(
    detections: Iterable[Detection],
) -> dict[DetectionType, int]:

    counter = Counter(
        detection.detection_type
        for detection in detections
    )

    return {
        detection_type: counter.get(
            detection_type,
            0,
        )
        for detection_type
        in DetectionType
    }