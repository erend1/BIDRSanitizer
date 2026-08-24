from bidr_sanitizer.models import (
    BoundingBox,
    DetectionType,
)
from bidr_sanitizer.ocr.mapping import (
    build_search_index,
    map_text_detections_to_image,
)
from bidr_sanitizer.ocr.models import OCRTextItem
from bidr_sanitizer.recognizers.structured import (
    recognize_structured_pii,
)


def test_phone_detection_maps_back_to_ocr_box():
    items = [
        OCRTextItem(
            text="Telefon: 0532 123 45 67",
            bbox=BoundingBox(
                x1=20,
                y1=30,
                x2=300,
                y2=70,
            ),
            confidence=0.98,
        )
    ]

    index = build_search_index(items)

    text_detections = recognize_structured_pii(
        index.text
    )

    detections = map_text_detections_to_image(
        text_detections,
        items,
        index,
    )

    assert len(detections) == 1

    detection = detections[0]

    assert (
        detection.detection_type
        == DetectionType.PHONE
    )

    assert detection.bbox == BoundingBox(
        x1=20,
        y1=30,
        x2=300,
        y2=70,
    )


def test_detection_can_span_multiple_ocr_regions():
    items = [
        OCRTextItem(
            text="T.C. Kimlik No:",
            bbox=BoundingBox(
                x1=10,
                y1=10,
                x2=150,
                y2=40,
            ),
            confidence=0.99,
        ),
        OCRTextItem(
            text="12345678901",
            bbox=BoundingBox(
                x1=160,
                y1=10,
                x2=300,
                y2=40,
            ),
            confidence=0.97,
        ),
    ]

    index = build_search_index(items)

    text_detections = recognize_structured_pii(
        index.text
    )

    detections = map_text_detections_to_image(
        text_detections,
        items,
        index,
    )

    assert len(detections) == 1

    assert (
        detections[0].detection_type
        == DetectionType.TCKN
    )