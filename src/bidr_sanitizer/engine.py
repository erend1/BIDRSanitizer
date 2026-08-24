from __future__ import annotations

from pathlib import Path

from bidr_sanitizer.config import (
    YUNET_MODEL_PATH,
)
from bidr_sanitizer.ocr.paddle_adapter import (
    PaddleOCRAdapter,
)
from bidr_sanitizer.pipeline import (
    SanitizationResult,
    sanitize_and_verify_image,
)
from bidr_sanitizer.review.image_workflow import (
    analyze_image_for_review,
    export_reviewed_image,
)
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ReviewedImageExportResult,
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


class OfflineImageSanitizer:
    """
    Complete local/offline sanitizer for PNG/JPEG images.

    Models are initialized once and reused for every image processed
    by this object.
    """

    def __init__(self) -> None:
        self._ocr = PaddleOCRAdapter()

        self._semantic_recognizer = (
            GLiNERPIIRecognizer()
        )

        self._face_detector = (
            YuNetFaceDetector(
                YUNET_MODEL_PATH
            )
        )

        self._signature_detector = (
            YOLOSSignatureDetector()
        )

    @property
    def semantic_recognizer(
        self
    ):
        return self._semantic_recognizer
    
    def sanitize(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        margin: int = 5,
        max_redaction_passes: int = 3,
    ) -> SanitizationResult:

        return sanitize_and_verify_image(
            input_path=input_path,
            output_path=output_path,
            margin=margin,
            ocr=self._ocr,
            semantic_recognizer=(
                self._semantic_recognizer
            ),
            face_detector=(
                self._face_detector
            ),
            signature_detector=(
                self._signature_detector
            ),
            max_redaction_passes=(
                max_redaction_passes
            ),
        )

    def analyze_for_review(
        self,
        input_path: str | Path,
        *,
        settings: ImageSanitizerSettings | None = None,
    ) -> ImageReviewPlan:
        return analyze_image_for_review(
            input_path,
            ocr=self._ocr,
            settings=settings,
            semantic_recognizer=self._semantic_recognizer,
            face_detector=self._face_detector,
            signature_detector=self._signature_detector,
        )

    def export_reviewed(
        self,
        input_path: str | Path,
        output_path: str | Path,
        plan: ImageReviewPlan,
    ) -> ReviewedImageExportResult:
        return export_reviewed_image(
            input_path,
            output_path,
            plan,
            ocr=self._ocr,
            semantic_recognizer=self._semantic_recognizer,
            face_detector=self._face_detector,
            signature_detector=self._signature_detector,
        )
