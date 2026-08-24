from bidr_sanitizer.engine import (
    OfflineImageSanitizer,
)
from bidr_sanitizer.word.sanitizer import (
    sanitize_word_document,
)
from bidr_sanitizer.word.word_com import (
    WordCOMConverter,
)


image_sanitizer = (
    OfflineImageSanitizer()
)

word_converter = (
    WordCOMConverter()
)


result = sanitize_word_document(
    "samples/test_evidence.docx",
    "output/test_evidence_REDACTED.pdf",
    converter=word_converter,
    sanitizer=image_sanitizer,
    dpi=300,
)


print()
print(
    "=== WORD SANITIZER RESULT ==="
)

print(
    "Source format:",
    result.source_format,
)

print(
    "Pages:",
    result.page_count,
)

print(
    "Text layer empty:",
    result.pdf_result.text_layer_empty,
)


if result.passed:
    print(
        "WORD VERIFICATION: PASSED"
    )
else:
    print(
        "WORD VERIFICATION: "
        "REVIEW REQUIRED"
    )