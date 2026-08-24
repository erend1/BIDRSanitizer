from __future__ import annotations

from pathlib import Path

from bidr_sanitizer.ocr.base import OCRProvider
from bidr_sanitizer.verification.models import (
    VerificationReport,
)
from bidr_sanitizer.models import Detection
from bidr_sanitizer.vision.base import (
    FaceDetectorProvider,
)
from bidr_sanitizer.text_detection import (
    detect_text_pii_from_ocr_items,
)


def verify_image(
    image_path: str | Path,
    *,
    ocr: OCRProvider,
    semantic_recognizer: SemanticPIIRecognizer | None = None,
    face_detector: FaceDetectorProvider | None = None,
    signature_detector: SignatureDetectorProvider | None = None,
) -> VerificationReport:

    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(image_path)

    remaining: list[Detection] = []

    # -----------------------------
    # Structured text verification
    # -----------------------------

    ocr_items = ocr.recognize(
        image_path
    )

    if ocr_items:
        remaining.extend(
            detect_text_pii_from_ocr_items(
                ocr_items,
                semantic_recognizer=semantic_recognizer,
            )
        )

    # -----------------------------
    # Face verification
    # -----------------------------

    if face_detector is not None:
        remaining.extend(
            face_detector.detect(
                image_path
            )
        )
    
    # -----------------------------
    # Signature verification
    # -----------------------------

    if signature_detector is not None:
        remaining.extend(
            signature_detector.detect(
                image_path
            )
        )
    
    return VerificationReport(
        remaining_detections=tuple(
            remaining
        )
    )