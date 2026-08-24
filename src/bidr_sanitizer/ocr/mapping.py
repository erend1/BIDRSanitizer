from __future__ import annotations

from collections.abc import Sequence

from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    TextDetection,
)
from bidr_sanitizer.ocr.models import (
    OCRSearchIndex,
    OCRTextItem,
)


def build_search_index(
    items: Sequence[OCRTextItem],
) -> OCRSearchIndex:
    """
    Build one temporary searchable string from OCR regions while
    remembering which character ranges belong to which image boxes.
    """

    chunks: list[str] = []
    spans: list[tuple[int, int]] = []

    cursor = 0

    for index, item in enumerate(items):
        if index > 0:
            separator = "\n"
            chunks.append(separator)
            cursor += len(separator)

        start = cursor

        chunks.append(item.text)
        cursor += len(item.text)

        end = cursor

        spans.append((start, end))

    return OCRSearchIndex(
        text="".join(chunks),
        item_spans=tuple(spans),
    )


def _spans_overlap(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> bool:
    return (
        first_start < second_end
        and second_start < first_end
    )


def _union_boxes(
    boxes: Sequence[BoundingBox],
) -> BoundingBox:
    if not boxes:
        raise ValueError(
            "At least one bounding box is required."
        )

    return BoundingBox(
        x1=min(box.x1 for box in boxes),
        y1=min(box.y1 for box in boxes),
        x2=max(box.x2 for box in boxes),
        y2=max(box.y2 for box in boxes),
    )


def map_text_detections_to_image(
    text_detections: Sequence[TextDetection],
    items: Sequence[OCRTextItem],
    search_index: OCRSearchIndex,
) -> list[Detection]:
    """
    Convert character-level PII detections into pixel-level
    image detections.
    """

    if len(items) != len(search_index.item_spans):
        raise ValueError(
            "OCR items and search-index spans do not match."
        )

    detections: list[Detection] = []

    for text_detection in text_detections:
        matching_items: list[OCRTextItem] = []

        for item, (
            item_start,
            item_end,
        ) in zip(
            items,
            search_index.item_spans,
            strict=True,
        ):
            if _spans_overlap(
                text_detection.span.start,
                text_detection.span.end,
                item_start,
                item_end,
            ):
                matching_items.append(item)

        if not matching_items:
            continue

        bbox = _union_boxes(
            [item.bbox for item in matching_items]
        )

        ocr_confidence = min(
            item.confidence
            for item in matching_items
        )

        detections.append(
            Detection(
                detection_type=text_detection.detection_type,
                bbox=bbox,
                confidence=min(
                    text_detection.confidence,
                    ocr_confidence,
                ),
            )
        )

    return detections