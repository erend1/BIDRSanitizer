from __future__ import annotations

import re
from collections.abc import Sequence

from bidr_sanitizer.models import (
    Detection,
    DetectionType,
)
from bidr_sanitizer.ocr.models import OCRTextItem


ADDRESS_HEADER_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        ikamet\s+adresi
        |
        ev\s+adresi
        |
        yerleşim\s+yeri(?:\s+adresi)?
        |
        tebligat\s+adresi
        |
        açık\s+adres
        |
        adres
    )
    \s*[:\-]?
    """,
    re.IGNORECASE | re.VERBOSE,
)


STOP_HEADER_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        telefon
        |
        tel\.?
        |
        gsm
        |
        cep
        |
        e-?posta
        |
        e-?mail
        |
        t\.?\s*c\.?
        |
        tc
        |
        tckn
        |
        imza
        |
        tarih
        |
        adı?\s+soyadı?
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def detect_address_blocks(
    items: Sequence[OCRTextItem],
    *,
    max_following_lines: int = 5,
    max_vertical_gap_ratio: float = 2.5,
) -> list[Detection]:
    """
    Detect address blocks beginning with explicit address headers.

    This is deliberately high-recall. Once an address header is found,
    nearby following OCR lines are treated as part of the address until
    a likely new field or a large vertical gap is encountered.
    """

    detections: list[Detection] = []

    remaining_lines = 0
    previous_item: OCRTextItem | None = None

    for item in items:
        text = item.text.strip()

        is_address_header = bool(
            ADDRESS_HEADER_PATTERN.match(text)
        )

        if is_address_header:
            detections.append(
                Detection(
                    detection_type=DetectionType.ADDRESS,
                    bbox=item.bbox,
                    confidence=item.confidence,
                )
            )

            remaining_lines = max_following_lines
            previous_item = item
            continue

        if remaining_lines <= 0:
            continue

        if STOP_HEADER_PATTERN.match(text):
            remaining_lines = 0
            previous_item = None
            continue

        if previous_item is not None:
            vertical_gap = (
                item.bbox.y1
                - previous_item.bbox.y2
            )

            reference_height = max(
                previous_item.bbox.height,
                item.bbox.height,
                1,
            )

            if (
                vertical_gap
                > reference_height
                * max_vertical_gap_ratio
            ):
                remaining_lines = 0
                previous_item = None
                continue

        detections.append(
            Detection(
                detection_type=DetectionType.ADDRESS,
                bbox=item.bbox,
                confidence=item.confidence,
            )
        )

        remaining_lines -= 1
        previous_item = item

    return detections