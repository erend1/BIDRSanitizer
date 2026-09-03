from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bidr_sanitizer.models import Detection
from bidr_sanitizer.ocr.base import OCRProvider
from bidr_sanitizer.ocr.paddle_adapter import (
    PaddleOCRAdapter,
)
from bidr_sanitizer.redaction import (
    ImageOutputTransform,
    redact_image_file,
)
from bidr_sanitizer.verification.models import (
    VerificationReport,
)
from bidr_sanitizer.verification.verifier import (
    verify_image,
)
from bidr_sanitizer.vision.base import (
    FaceDetectorProvider,
    SignatureDetectorProvider,
)
from bidr_sanitizer.recognizers.semantic.base import (
    SemanticPIIRecognizer,
)
from bidr_sanitizer.text_detection import (
    detect_text_pii_from_ocr_items,
)


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    output_path: Path
    applied_detections: tuple[Detection, ...]
    verification: VerificationReport
    redaction_passes: int

    @property
    def passed(self) -> bool:
        return self.verification.passed


def detect_text_pii_in_image(
    input_path: str | Path,
    *,
    ocr: OCRProvider,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
) -> list[Detection]:

    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    ocr_items = ocr.recognize(
        input_path
    )

    return detect_text_pii_from_ocr_items(
        ocr_items,
        semantic_recognizer=semantic_recognizer,
    )


def detect_image_pii(
    input_path: str | Path,
    *,
    ocr: OCRProvider,
    semantic_recognizer: SemanticPIIRecognizer | None = None,
    face_detector: FaceDetectorProvider | None = None,
    signature_detector: SignatureDetectorProvider | None = None,
) -> list[Detection]:
    """Run every configured image detector without performing redaction."""

    detections = detect_text_pii_in_image(
        input_path,
        ocr=ocr,
        semantic_recognizer=semantic_recognizer,
    )

    if face_detector is not None:
        detections.extend(face_detector.detect(input_path))

    if signature_detector is not None:
        detections.extend(signature_detector.detect(input_path))

    return detections


def sanitize_image(
    input_path: str | Path,
    output_path: str | Path,
    *,
    margin: int = 5,
    ocr: OCRProvider | None = None,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
    face_detector: (
        FaceDetectorProvider | None
    ) = None,
    signature_detector: (
        SignatureDetectorProvider | None
    ) = None,
    output_transform: ImageOutputTransform | None = None,
) -> list[Detection]:

    if ocr is None:
        ocr = PaddleOCRAdapter()

    detections = detect_image_pii(
        input_path,
        ocr=ocr,
        semantic_recognizer=semantic_recognizer,
        face_detector=face_detector,
        signature_detector=signature_detector,
    )
    
    redact_image_file(
        input_path=input_path,
        output_path=output_path,
        detections=detections,
        margin=margin,
        output_transform=output_transform,
    )

    return detections


def sanitize_and_verify_image(
    input_path: str | Path,
    output_path: str | Path,
    *,
    margin: int = 5,
    ocr: OCRProvider | None = None,
    semantic_recognizer: (
        SemanticPIIRecognizer | None
    ) = None,
    face_detector: (
        FaceDetectorProvider | None
    ) = None,
    max_redaction_passes: int = 3,
    signature_detector: (
        SignatureDetectorProvider | None
    ) = None,
    output_transform: ImageOutputTransform | None = None,
) -> SanitizationResult:

    input_path = Path(input_path)
    output_path = Path(output_path)

    if max_redaction_passes < 1:
        raise ValueError(
            "max_redaction_passes must be at least 1."
        )

    if input_path.resolve() == output_path.resolve():
        raise ValueError(
            "Input and output paths must be different."
        )

    if ocr is None:
        ocr = PaddleOCRAdapter()

    # -------------------------------------------------
    # First pass
    # -------------------------------------------------

    applied = sanitize_image(
        input_path=input_path,
        output_path=output_path,
        margin=margin,
        ocr=ocr,
        semantic_recognizer=semantic_recognizer,
        face_detector=face_detector,
        signature_detector=signature_detector,
        output_transform=output_transform,
    )

    all_applied = list(applied)

    redaction_passes = 1

    verification = verify_image(
        output_path,
        ocr=ocr,
        semantic_recognizer=semantic_recognizer,
        face_detector=face_detector,
        signature_detector=signature_detector,
    )

    # -------------------------------------------------
    # Remediation passes
    # -------------------------------------------------

    while (
        not verification.passed
        and redaction_passes
        < max_redaction_passes
    ):
        existing_keys = {
            (
                detection.detection_type,
                detection.bbox.x1,
                detection.bbox.y1,
                detection.bbox.x2,
                detection.bbox.y2,
            )
            for detection in all_applied
        }

        newly_found = [
            detection
            for detection
            in verification.remaining_detections
            if (
                detection.detection_type,
                detection.bbox.x1,
                detection.bbox.y1,
                detection.bbox.x2,
                detection.bbox.y2,
            )
            not in existing_keys
        ]

        # If verification keeps reporting exactly the same
        # already-redacted location, another pass cannot help.
        if not newly_found:
            break

        all_applied.extend(
            newly_found
        )

        # Always redraw from the ORIGINAL image.
        #
        # This avoids repeatedly JPEG-compressing the already
        # redacted output.
        redact_image_file(
            input_path=input_path,
            output_path=output_path,
            detections=all_applied,
            margin=margin,
            output_transform=output_transform,
        )

        redaction_passes += 1

        verification = verify_image(
            output_path,
            ocr=ocr,
            semantic_recognizer=semantic_recognizer,
            face_detector=face_detector,
            signature_detector=signature_detector,
        )

    return SanitizationResult(
        output_path=output_path,
        applied_detections=tuple(
            all_applied
        ),
        verification=verification,
        redaction_passes=redaction_passes,
    )
