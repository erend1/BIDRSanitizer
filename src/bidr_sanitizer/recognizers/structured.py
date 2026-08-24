from __future__ import annotations

import re
from collections.abc import Iterable

from bidr_sanitizer.models import (
    DetectionType,
    TextDetection,
    TextSpan,
)


# ---------------------------------------------------------------------------
# TCKN
# ---------------------------------------------------------------------------

TCKN_CANDIDATE_PATTERN = re.compile(
    r"(?<!\d)(?P<candidate>\d(?:[\s.\-]?\d){10})(?!\d)"
)

TCKN_CONTEXT_PATTERN = re.compile(
    r"""
    (?:
        \bT\.?\s*C\.?\b
        |
        \bTC\b
        |
        \bTCKN\b
        |
        \bT\.?\s*C\.?\s*Kimlik\b
        |
        \bKimlik\s*(?:No|Numarası|Numarasi)\b
        |
        \bKimlik\s*(?:No|Numarası|Numarasi)\s*[:.]?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_digits(value: str) -> str:
    """
    Remove every non-digit character.

    Examples:
        '0532 123 45 67' -> '05321234567'
        '123.456.789.01' -> '12345678901'
    """
    return re.sub(r"\D", "", value)


def is_valid_tckn(value: str) -> bool:
    """
    Validate a Turkish Republic Identity Number using its checksum rules.

    This function performs only mathematical validation. It does not verify
    whether the number belongs to a real person.
    """
    digits = normalize_digits(value)

    if len(digits) != 11:
        return False

    if digits[0] == "0":
        return False

    if not digits.isdigit():
        return False

    numbers = [int(digit) for digit in digits]

    odd_sum = sum(numbers[0:9:2])
    even_sum = sum(numbers[1:8:2])

    expected_tenth = ((odd_sum * 7) - even_sum) % 10

    if numbers[9] != expected_tenth:
        return False

    expected_eleventh = sum(numbers[:10]) % 10

    return numbers[10] == expected_eleventh


def _has_tckn_context(
    text: str,
    start: int,
    end: int,
    *,
    radius: int = 40,
) -> bool:
    context_start = max(0, start - radius)
    context_end = min(len(text), end + radius)

    context = text[context_start:context_end]

    return bool(TCKN_CONTEXT_PATTERN.search(context))


def recognize_tckn(text: str) -> list[TextDetection]:
    detections: list[TextDetection] = []

    for match in TCKN_CANDIDATE_PATTERN.finditer(text):
        candidate = match.group("candidate")

        checksum_valid = is_valid_tckn(candidate)
        context_present = _has_tckn_context(
            text,
            match.start(),
            match.end(),
        )

        # High-recall policy:
        #
        # 1. A checksum-valid standalone TCKN is sensitive.
        # 2. An 11-digit candidate explicitly labelled as a TC/TCKN value
        #    is also treated as sensitive even if mistyped.
        if not checksum_valid and not context_present:
            continue

        confidence = 1.0 if checksum_valid else 0.95

        detections.append(
            TextDetection(
                detection_type=DetectionType.TCKN,
                span=TextSpan(
                    start=match.start(),
                    end=match.end(),
                ),
                confidence=confidence,
            )
        )

    return detections


# ---------------------------------------------------------------------------
# Turkish phone numbers
# ---------------------------------------------------------------------------

PHONE_PATTERN = re.compile(
    r"""
    (?<!\d)

    (?:
        (?:
            \+90
            |
            0090
        )
        [\s.\-]*
    )?

    0?

    \(?
        (?P<prefix>[2345]\d{2})
    \)?

    [\s.\-]*

    (?P<part1>\d{3})

    [\s.\-]*

    (?P<part2>\d{2})

    [\s.\-]*

    (?P<part3>\d{2})

    (?!\d)
    """,
    re.VERBOSE,
)


def recognize_phone_numbers(text: str) -> list[TextDetection]:
    detections: list[TextDetection] = []

    for match in PHONE_PATTERN.finditer(text):
        detections.append(
            TextDetection(
                detection_type=DetectionType.PHONE,
                span=TextSpan(
                    start=match.start(),
                    end=match.end(),
                ),
                confidence=1.0,
            )
        )

    return detections


# ---------------------------------------------------------------------------
# E-mail addresses
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"""
    (?<![A-Za-z0-9._%+\-])

    [A-Za-z0-9._%+\-]+

    @

    [A-Za-z0-9.\-]+

    \.

    [A-Za-z]{2,}

    (?![A-Za-z0-9._%+\-])
    """,
    re.IGNORECASE | re.VERBOSE,
)


def recognize_emails(text: str) -> list[TextDetection]:
    detections: list[TextDetection] = []

    for match in EMAIL_PATTERN.finditer(text):
        detections.append(
            TextDetection(
                detection_type=DetectionType.EMAIL,
                span=TextSpan(
                    start=match.start(),
                    end=match.end(),
                ),
                confidence=1.0,
            )
        )

    return detections


# ---------------------------------------------------------------------------
# Combined structured recognizer
# ---------------------------------------------------------------------------

def _remove_exact_duplicates(
    detections: Iterable[TextDetection],
) -> list[TextDetection]:
    unique: dict[
        tuple[DetectionType, int, int],
        TextDetection,
    ] = {}

    for detection in detections:
        key = (
            detection.detection_type,
            detection.span.start,
            detection.span.end,
        )

        existing = unique.get(key)

        if existing is None or detection.confidence > existing.confidence:
            unique[key] = detection

    return sorted(
        unique.values(),
        key=lambda item: (
            item.span.start,
            item.span.end,
            item.detection_type.value,
        ),
    )


def recognize_structured_pii(text: str) -> list[TextDetection]:
    """
    Detect deterministic / structured PII.

    No detected sensitive value is stored in the returned objects.
    """
    detections = [
        *recognize_tckn(text),
        *recognize_phone_numbers(text),
        *recognize_emails(text),
    ]

    return _remove_exact_duplicates(detections)