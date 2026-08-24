from __future__ import annotations

from collections.abc import Iterable

from bidr_sanitizer.models import (
    TextDetection,
)
from bidr_sanitizer.recognizers.semantic.base import (
    SemanticPIIRecognizer,
)
from bidr_sanitizer.recognizers.structured import (
    recognize_structured_pii,
)


def _deduplicate_text_detections(
    detections: Iterable[TextDetection],
) -> list[TextDetection]:
    """
    Remove exact duplicate text detections while keeping the
    highest-confidence detection.
    """

    unique: dict[
        tuple,
        TextDetection,
    ] = {}

    for detection in detections:
        key = (
            detection.detection_type,
            detection.span.start,
            detection.span.end,
        )

        existing = unique.get(key)

        if (
            existing is None
            or detection.confidence
            > existing.confidence
        ):
            unique[key] = detection

    return sorted(
        unique.values(),
        key=lambda item: (
            item.span.start,
            item.span.end,
        ),
    )


def detect_pii_in_text(
    text: str,
    *,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
) -> list[TextDetection]:
    """
    Detect structured and semantic PII in ordinary text.
    """

    if not text:
        return []

    detections = list(
        recognize_structured_pii(
            text
        )
    )

    if semantic_recognizer is not None:
        detections.extend(
            semantic_recognizer.recognize(
                text
            )
        )

    return _deduplicate_text_detections(
        detections
    )