from bidr_sanitizer.text.sanitizer import (
    redact_text,
    sanitize_text,
)
from bidr_sanitizer.models import (
    DetectionType,
    TextDetection,
    TextSpan,
)


def test_redact_text_replaces_sensitive_span():
    text = (
        "Telefon: 0532 123 45 67"
    )

    start = text.index(
        "0532"
    )

    detection = TextDetection(
        detection_type=(
            DetectionType.PHONE
        ),
        span=TextSpan(
            start=start,
            end=len(text),
        ),
        confidence=1.0,
    )

    result = redact_text(
        text,
        [detection],
    )

    assert result == (
        "Telefon: [REDACTED]"
    )


def test_overlapping_text_spans_are_merged():
    text = "Ahmet Yılmaz"

    detections = [
        TextDetection(
            detection_type=DetectionType.PERSON,
            span=TextSpan(
                0,
                len(text),
            ),
            confidence=0.9,
        ),
        TextDetection(
            detection_type=DetectionType.PERSON,
            span=TextSpan(
                0,
                5,
            ),
            confidence=0.8,
        ),
    ]

    result = redact_text(
        text,
        detections,
    )

    assert result == "[REDACTED]"


def test_structured_text_is_sanitized():
    text = (
        "Telefon: 0532 123 45 67\n"
        "E-posta: person@example.com"
    )

    (
        result,
        detections,
        verification,
        passes,
    ) = sanitize_text(
        text
    )

    assert "0532" not in result
    assert "person@example.com" not in result

    assert verification.passed
    assert passes >= 1

    assert len(detections) == 2