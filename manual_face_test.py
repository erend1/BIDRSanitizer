from bidr_sanitizer.pipeline import (
    sanitize_and_verify_image,
)
from bidr_sanitizer.vision.yunet import (
    YuNetFaceDetector,
)
from bidr_sanitizer.config import (
    YUNET_MODEL_PATH,
)

face_detector = YuNetFaceDetector(
    YUNET_MODEL_PATH
)


result = sanitize_and_verify_image(
    "samples/test_faces.jpg",
    "output/test_faces_REDACTED.jpg",
    face_detector=face_detector,
)


print(
    "Redactions:",
    len(result.applied_detections),
)

for detection in (
    result.applied_detections
):
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

    print(
        "Remaining:",
        result.verification.remaining_count,
    )