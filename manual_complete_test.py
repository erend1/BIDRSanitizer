from bidr_sanitizer.audit import (
    count_detections,
)
from bidr_sanitizer.engine import (
    OfflineImageSanitizer,
)
from bidr_sanitizer.models import (
    DetectionType,
)


sanitizer = OfflineImageSanitizer()


result = sanitizer.sanitize(
    "samples/test_complete.png",
    "output/test_complete_REDACTED.png",
)


counts = count_detections(
    result.applied_detections
)


required_types = {
    DetectionType.TCKN,
    DetectionType.PHONE,
    DetectionType.EMAIL,
    DetectionType.PERSON,
    DetectionType.ADDRESS,
    DetectionType.FACE,
    DetectionType.SIGNATURE,
}


missing_types = {
    detection_type
    for detection_type in required_types
    if counts[detection_type] == 0
}


if missing_types:
    print()
    print(
        "MISSING EXPECTED CATEGORIES:"
    )

    for detection_type in sorted(
        missing_types,
        key=lambda item: item.value,
    ):
        print(
            "-",
            detection_type.value,
        )


print()
print("=== BIDR SANITIZER RESULT ===")
print()

for detection_type in DetectionType:
    print(
        f"{detection_type.value:12}",
        counts[detection_type],
    )


print()
print(
    "Redaction passes:",
    result.redaction_passes,
)

print(
    "Remaining detections:",
    result.verification.remaining_count,
)


if result.passed:
    print()
    print(
        "VERIFICATION: PASSED"
    )
else:
    print()
    print(
        "VERIFICATION: REVIEW REQUIRED"
    )