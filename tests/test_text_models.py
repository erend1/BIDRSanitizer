import pytest

from bidr_sanitizer.models import (
    DetectionType,
    TextDetection,
    TextSpan,
)


def test_text_span_length():
    span = TextSpan(
        start=10,
        end=25,
    )

    assert span.length == 15


def test_invalid_text_span_is_rejected():
    with pytest.raises(ValueError):
        TextSpan(
            start=20,
            end=10,
        )


def test_text_detection_confidence():
    detection = TextDetection(
        detection_type=DetectionType.EMAIL,
        span=TextSpan(
            start=0,
            end=10,
        ),
        confidence=0.95,
    )

    assert detection.confidence == 0.95


def test_invalid_text_confidence_is_rejected():
    with pytest.raises(ValueError):
        TextDetection(
            detection_type=DetectionType.EMAIL,
            span=TextSpan(
                start=0,
                end=10,
            ),
            confidence=1.5,
        )