from bidr_sanitizer.models import DetectionType
from bidr_sanitizer.recognizers.structured import (
    is_valid_tckn,
    recognize_tckn,
)


def build_checksum_valid_tckn(
    first_nine: str = "100000001",
) -> str:
    assert len(first_nine) == 9
    assert first_nine.isdigit()
    assert first_nine[0] != "0"

    digits = [int(value) for value in first_nine]

    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])

    tenth = ((odd_sum * 7) - even_sum) % 10

    first_ten = digits + [tenth]

    eleventh = sum(first_ten) % 10

    return "".join(
        str(value)
        for value in first_ten + [eleventh]
    )


def test_generated_tckn_is_checksum_valid():
    value = build_checksum_valid_tckn()

    assert is_valid_tckn(value)


def test_valid_tckn_is_detected_without_context():
    value = build_checksum_valid_tckn()

    text = f"Belge numarası {value} olarak kaydedilmiştir."

    detections = recognize_tckn(text)

    assert len(detections) == 1
    assert detections[0].detection_type == DetectionType.TCKN
    assert detections[0].confidence == 1.0


def test_spaced_tckn_is_detected():
    value = build_checksum_valid_tckn()

    spaced = " ".join(value)

    text = f"T.C. Kimlik No: {spaced}"

    detections = recognize_tckn(text)

    assert len(detections) == 1


def test_dotted_tckn_is_detected():
    value = build_checksum_valid_tckn()

    dotted = ".".join(value)

    text = f"TCKN: {dotted}"

    detections = recognize_tckn(text)

    assert len(detections) == 1


def test_invalid_unlabelled_eleven_digit_number_is_not_detected():
    text = "Referans numarası 12345678901 olarak kaydedildi."

    detections = recognize_tckn(text)

    assert detections == []


def test_invalid_checksum_is_still_detected_with_tckn_context():
    text = "T.C. Kimlik No: 12345678901"

    detections = recognize_tckn(text)

    assert len(detections) == 1
    assert detections[0].confidence == 0.95


def test_number_starting_with_zero_is_not_valid_tckn():
    assert not is_valid_tckn("01234567890")