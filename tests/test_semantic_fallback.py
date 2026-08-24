from bidr_sanitizer.models import (
    BoundingBox,
    DetectionType,
    TextDetection,
    TextSpan,
)
from bidr_sanitizer.ocr.models import (
    OCRTextItem,
)
from bidr_sanitizer.text_detection import (
    detect_text_pii_from_ocr_items,
)


class ContextSensitiveFakeRecognizer:
    """
    Simulates a semantic model that misses a person in
    document context but detects the isolated OCR line.
    """

    def recognize(
        self,
        text: str,
    ) -> list[TextDetection]:

        if text.strip() != "Ayşe Demir":
            return []

        return [
            TextDetection(
                detection_type=(
                    DetectionType.PERSON
                ),
                span=TextSpan(
                    start=0,
                    end=len("Ayşe Demir"),
                ),
                confidence=0.98,
            )
        ]


def test_isolated_name_fallback():
    items = [
        OCRTextItem(
            text="Toplantı Tutanağı",
            bbox=BoundingBox(
                10, 10, 200, 30
            ),
            confidence=0.99,
        ),
        OCRTextItem(
            text="Ayşe Demir",
            bbox=BoundingBox(
                10, 40, 150, 60
            ),
            confidence=0.99,
        ),
    ]

    detections = (
        detect_text_pii_from_ocr_items(
            items,
            semantic_recognizer=(
                ContextSensitiveFakeRecognizer()
            ),
        )
    )

    assert any(
        detection.detection_type
        == DetectionType.PERSON
        for detection in detections
    )