from bidr_sanitizer.config import (
    SIGNATURE_MODEL_DIR,
)
from bidr_sanitizer.vision.signature_yolos import (
    YOLOSSignatureDetector,
)


detector = YOLOSSignatureDetector(
    SIGNATURE_MODEL_DIR
)


detections = detector.detect(
    "samples/test_signatures.jpeg"
)


print(
    "Signatures detected:",
    len(detections),
)


for detection in detections:
    print(
        detection.detection_type.value,
        detection.bbox,
        round(
            detection.confidence,
            4,
        ),
    )