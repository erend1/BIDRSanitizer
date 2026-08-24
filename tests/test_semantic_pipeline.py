from pathlib import Path

from PIL import Image

from bidr_sanitizer.models import (
    BoundingBox,
    DetectionType,
    TextDetection,
    TextSpan,
)
from bidr_sanitizer.ocr.mapping import (
    build_search_index,
    map_text_detections_to_image,
)
from bidr_sanitizer.ocr.models import OCRTextItem


def test_person_span_maps_to_image_box():
    items = [
        OCRTextItem(
            text="Prof. Dr. Ahmet Yılmaz",
            bbox=BoundingBox(
                x1=20,
                y1=30,
                x2=300,
                y2=60,
            ),
            confidence=0.98,
        )
    ]

    index = build_search_index(items)

    start = index.text.index(
        "Ahmet Yılmaz"
    )

    end = start + len(
        "Ahmet Yılmaz"
    )

    semantic_detection = TextDetection(
        detection_type=DetectionType.PERSON,
        span=TextSpan(
            start=start,
            end=end,
        ),
        confidence=0.91,
    )

    detections = map_text_detections_to_image(
        [semantic_detection],
        items,
        index,
    )

    assert len(detections) == 1

    assert (
        detections[0].detection_type
        == DetectionType.PERSON
    )

    assert detections[0].bbox == BoundingBox(
        x1=20,
        y1=30,
        x2=300,
        y2=60,
    )


def test_address_span_maps_to_image_box():
    items = [
        OCRTextItem(
            text=(
                "Adres: Atatürk Mahallesi "
                "Gül Sokak No: 12 Maltepe İstanbul"
            ),
            bbox=BoundingBox(
                x1=20,
                y1=80,
                x2=600,
                y2=120,
            ),
            confidence=0.97,
        )
    ]

    index = build_search_index(items)

    start = index.text.index(
        "Atatürk Mahallesi"
    )

    end = len(index.text)

    semantic_detection = TextDetection(
        detection_type=(
            DetectionType.ADDRESS
        ),
        span=TextSpan(
            start=start,
            end=end,
        ),
        confidence=0.87,
    )

    detections = map_text_detections_to_image(
        [semantic_detection],
        items,
        index,
    )

    assert len(detections) == 1

    assert (
        detections[0].detection_type
        == DetectionType.ADDRESS
    )