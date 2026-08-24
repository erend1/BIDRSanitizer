import pytest

from bidr_sanitizer.models import DetectionType
from bidr_sanitizer.recognizers.structured import (
    recognize_phone_numbers,
)


@pytest.mark.parametrize(
    "phone",
    [
        "0532 123 45 67",
        "05321234567",
        "532 123 45 67",
        "5321234567",
        "+90 532 123 45 67",
        "+905321234567",
        "0090 532 123 45 67",
        "0212 123 45 67",
        "02121234567",
        "+90 212 123 45 67",
        "+90 (212) 123 45 67",
        "(216) 123 45 67",
        "0216-123-45-67",
    ],
)
def test_turkish_phone_formats_are_detected(phone):
    text = f"İletişim: {phone}"

    detections = recognize_phone_numbers(text)

    assert len(detections) == 1
    assert detections[0].detection_type == DetectionType.PHONE


@pytest.mark.parametrize(
    "value",
    [
        "12345",
        "123456789",
        "9999999999",
        "111 222 33 44",
        "1234 5678 9012",
    ],
)
def test_non_phone_values_are_not_detected(value):
    detections = recognize_phone_numbers(value)

    assert detections == []