import pytest

from bidr_sanitizer.models import DetectionType
from bidr_sanitizer.recognizers.structured import (
    recognize_emails,
)


@pytest.mark.parametrize(
    "email",
    [
        "name@example.com",
        "name.surname@example.com",
        "name_surname@example.com",
        "name-surname@example.com",
        "name+test@example.com",
        "person@rumeli.edu.tr",
        "someone123@subdomain.example.org",
    ],
)
def test_email_addresses_are_detected(email):
    text = f"İletişim adresi: {email}"

    detections = recognize_emails(text)

    assert len(detections) == 1
    assert detections[0].detection_type == DetectionType.EMAIL


@pytest.mark.parametrize(
    "value",
    [
        "example.com",
        "@example.com",
        "name@",
        "name@example",
        "name example.com",
    ],
)
def test_invalid_email_values_are_not_detected(value):
    assert recognize_emails(value) == []