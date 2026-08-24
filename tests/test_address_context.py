from bidr_sanitizer.models import (
    BoundingBox,
    DetectionType,
)
from bidr_sanitizer.ocr.models import OCRTextItem
from bidr_sanitizer.recognizers.address_context import (
    detect_address_blocks,
)


def test_multiline_home_address_is_detected():
    items = [
        OCRTextItem(
            text="İkamet Adresi:",
            bbox=BoundingBox(10, 10, 150, 30),
            confidence=0.99,
        ),
        OCRTextItem(
            text="Atatürk Mahallesi",
            bbox=BoundingBox(10, 35, 200, 55),
            confidence=0.99,
        ),
        OCRTextItem(
            text="Gül Sokak No: 12 Daire: 4",
            bbox=BoundingBox(10, 60, 300, 80),
            confidence=0.99,
        ),
        OCRTextItem(
            text="Maltepe / İstanbul",
            bbox=BoundingBox(10, 85, 200, 105),
            confidence=0.99,
        ),
    ]

    detections = detect_address_blocks(
        items
    )

    assert len(detections) == 4

    assert all(
        detection.detection_type
        == DetectionType.ADDRESS
        for detection in detections
    )


def test_normal_use_of_word_address_is_not_detected():
    items = [
        OCRTextItem(
            text=(
                "İstanbul adresindeki "
                "toplantıya katılım sağlandı."
            ),
            bbox=BoundingBox(
                10, 10, 400, 30
            ),
            confidence=0.99,
        ),
    ]

    detections = detect_address_blocks(
        items
    )

    assert detections == []