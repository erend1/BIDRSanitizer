from bidr_sanitizer.audit import (
    count_detections,
)
from bidr_sanitizer.engine import (
    OfflineImageSanitizer,
)
from bidr_sanitizer.models import (
    DetectionType,
)
from bidr_sanitizer.pdf.sanitizer import (
    sanitize_pdf,
)


sanitizer = (
    OfflineImageSanitizer()
)


result = sanitize_pdf(
    "samples/test_evidence.pdf",
    "output/test_evidence_REDACTED.pdf",
    sanitizer=sanitizer,
    dpi=300,
)


print()
print(
    "=== PDF SANITIZER RESULT ==="
)

print(
    "Pages:",
    result.page_count,
)

print(
    "Text layer empty:",
    result.text_layer_empty,
)


for page in result.pages:
    counts = count_detections(
        page
        .sanitization
        .applied_detections
    )

    print()
    print(
        f"--- PAGE "
        f"{page.page_number} ---"
    )

    for detection_type in (
        DetectionType
    ):
        count = counts[
            detection_type
        ]

        if count > 0:
            print(
                f"{detection_type.value:12}"
                f" {count}"
            )

    print(
        "passes:",
        page
        .sanitization
        .redaction_passes,
    )


print()

if result.passed:
    print(
        "PDF VERIFICATION: PASSED"
    )
else:
    print(
        "PDF VERIFICATION: "
        "REVIEW REQUIRED"
    )