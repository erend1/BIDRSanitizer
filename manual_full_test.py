from bidr_sanitizer.pipeline import (
    sanitize_and_verify_image,
)
from bidr_sanitizer.ocr.paddle_adapter import (
    PaddleOCRAdapter,
)
from bidr_sanitizer.recognizers.semantic.gliner_adapter import (
    GLiNERPIIRecognizer,
)
from bidr_sanitizer.vision.signature_yolos import (
    YOLOSSignatureDetector,
)
from bidr_sanitizer.vision.yunet import (
    YuNetFaceDetector,
)
from bidr_sanitizer.config import (
    YUNET_MODEL_PATH,
)


ocr = PaddleOCRAdapter()

ner = GLiNERPIIRecognizer()

face_detector = YuNetFaceDetector(
    YUNET_MODEL_PATH
)

signature_detector = (
    YOLOSSignatureDetector()
)

result = sanitize_and_verify_image(
    "samples/test_full.png",
    "output/test_full_REDACTED.png",
    ocr=ocr,
    semantic_recognizer=ner,
    face_detector=face_detector,
    signature_detector=signature_detector,
)


print(
    "Applied redactions:",
    len(result.applied_detections),
)

for detection in result.applied_detections:
    print(
        detection.detection_type.value,
        detection.bbox,
        round(
            detection.confidence,
            4,
        ),
    )


print()

if result.passed:
    print("VERIFICATION: PASSED")
else:
    print(
        "VERIFICATION: REVIEW REQUIRED"
    )

    for detection in (
        result.verification.remaining_detections
    ):
        print(
            detection.detection_type.value,
            detection.bbox,
            round(
                detection.confidence,
                4,
            ),
        )

print(
    "Redaction passes:",
    result.redaction_passes,
)
