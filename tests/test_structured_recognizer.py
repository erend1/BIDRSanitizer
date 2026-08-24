from bidr_sanitizer.models import DetectionType
from bidr_sanitizer.recognizers.structured import (
    recognize_structured_pii,
)


def test_combined_recognizer_detects_multiple_pii_types():
    text = """
    T.C. Kimlik No: 12345678901
    Telefon: +90 532 123 45 67
    E-posta: name.surname@rumeli.edu.tr
    """

    detections = recognize_structured_pii(text)

    detected_types = {
        detection.detection_type
        for detection in detections
    }

    assert DetectionType.TCKN in detected_types
    assert DetectionType.PHONE in detected_types
    assert DetectionType.EMAIL in detected_types


def test_combined_results_are_sorted_by_position():
    text = """
    Mail: person@example.com
    Telefon: 0532 123 45 67
    """

    detections = recognize_structured_pii(text)

    starts = [
        detection.span.start
        for detection in detections
    ]

    assert starts == sorted(starts)


def test_detector_does_not_store_sensitive_text():
    text = "Telefon: 0532 123 45 67"

    detections = recognize_structured_pii(text)

    assert len(detections) == 1

    detection = detections[0]

    assert not hasattr(detection, "text")
    assert not hasattr(detection, "value")
    assert not hasattr(detection, "matched_text")