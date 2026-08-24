from __future__ import annotations

from collections.abc import Sequence

from bidr_sanitizer.models import Detection
from bidr_sanitizer.ocr.mapping import (
    build_search_index,
    map_text_detections_to_image,
)
from bidr_sanitizer.ocr.models import OCRTextItem
from bidr_sanitizer.recognizers.address_context import (
    detect_address_blocks,
)
from bidr_sanitizer.recognizers.semantic.base import (
    SemanticPIIRecognizer,
)
from bidr_sanitizer.recognizers.structured import (
    recognize_structured_pii,
)


def _detection_key(
    detection: Detection,
) -> tuple:
    return (
        detection.detection_type,
        detection.bbox.x1,
        detection.bbox.y1,
        detection.bbox.x2,
        detection.bbox.y2,
    )


def _deduplicate(
    detections: Sequence[Detection],
) -> list[Detection]:
    unique: dict[tuple, Detection] = {}

    for detection in detections:
        key = _detection_key(detection)

        existing = unique.get(key)

        if (
            existing is None
            or detection.confidence
            > existing.confidence
        ):
            unique[key] = detection

    return list(unique.values())


def _should_run_line_semantics(
    text: str,
) -> bool:
    """
    Short OCR regions are particularly important for isolated names
    such as 'Ayşe Demir'.
    """

    stripped = text.strip()

    if not stripped:
        return False

    if len(stripped) > 120:
        return False

    if len(stripped.split()) > 12:
        return False

    return True


def detect_text_pii_from_ocr_items(
    items: Sequence[OCRTextItem],
    *,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
) -> list[Detection]:

    if not items:
        return []

    detections: list[Detection] = []

    # -------------------------------------------------
    # 1. Full-document structured recognition
    # -------------------------------------------------

    search_index = build_search_index(items)

    structured = recognize_structured_pii(
        search_index.text
    )

    detections.extend(
        map_text_detections_to_image(
            structured,
            items,
            search_index,
        )
    )

    # -------------------------------------------------
    # 2. Deterministic address-block fallback
    # -------------------------------------------------

    detections.extend(
        detect_address_blocks(items)
    )

    if semantic_recognizer is not None:

        # ---------------------------------------------
        # 3. Full-document semantic recognition
        # ---------------------------------------------

        semantic = (
            semantic_recognizer.recognize(
                search_index.text
            )
        )

        detections.extend(
            map_text_detections_to_image(
                semantic,
                items,
                search_index,
            )
        )

        # ---------------------------------------------
        # 4. Per-line semantic fallback
        #
        # Important for isolated names that may be
        # missed when processed inside a large document.
        # ---------------------------------------------

        for item in items:
            if not _should_run_line_semantics(
                item.text
            ):
                continue

            local_index = build_search_index(
                [item]
            )

            local_semantic = (
                semantic_recognizer.recognize(
                    local_index.text
                )
            )

            detections.extend(
                map_text_detections_to_image(
                    local_semantic,
                    [item],
                    local_index,
                )
            )

    return _deduplicate(detections)