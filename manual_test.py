from bidr_sanitizer.pipeline import (
    sanitize_and_verify_image,
)


result = sanitize_and_verify_image(
    "samples/test_pii.png",
    "output/test_pii_REDACTED.png",
)


print(
    f"Redactions applied: "
    f"{len(result.applied_detections)}"
)

for detection in result.applied_detections:
    print(
        detection.detection_type.value,
        detection.bbox,
        detection.confidence,
    )


print()

if result.passed:
    print("VERIFICATION: PASSED")
else:
    print(
        "VERIFICATION: REVIEW REQUIRED"
    )

    print(
        "Remaining detections:",
        result.verification.remaining_count,
    )

    for detection in (
        result.verification.remaining_detections
    ):
        print(
            detection.detection_type.value,
            detection.bbox,
            detection.confidence,
        )