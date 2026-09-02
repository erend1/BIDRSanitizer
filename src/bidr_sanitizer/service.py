from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from bidr_sanitizer.review.models import (
        ImageReviewPlan,
        ImageSanitizerSettings,
        ReviewedImageExportResult,
    )


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
}

PDF_EXTENSIONS = {
    ".pdf",
}

WORD_EXTENSIONS = {
    ".doc",
    ".docx",
}

TEXT_EXTENSIONS = {
    ".txt",
}

SUPPORTED_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | PDF_EXTENSIONS
    | WORD_EXTENSIONS
    | TEXT_EXTENSIONS
)


class BIDRSanitizerService:
    """
    Long-lived sanitizer service.

    Heavy AI models are initialized once and reused across files.
    """

    def __init__(self) -> None:
        self._image_sanitizer = None
        self._semantic_recognizer = None
        self._word_converter = None

    def _get_image_sanitizer(self):
        if self._image_sanitizer is None:
            from bidr_sanitizer.engine import (
                OfflineImageSanitizer,
            )

            self._image_sanitizer = (
                OfflineImageSanitizer()
            )

        return self._image_sanitizer

    def _get_semantic_recognizer(self):
        if (
            self._semantic_recognizer
            is None
        ):
            from bidr_sanitizer.recognizers.semantic.gliner_adapter import (
                GLiNERPIIRecognizer
            )

            self._semantic_recognizer = (
                GLiNERPIIRecognizer()
            )

        return (
            self._semantic_recognizer
        )

    def _get_word_converter(self):
        if self._word_converter is None:
            from bidr_sanitizer.word.word_com import (
                WordCOMConverter,
            )

            self._word_converter = (
                WordCOMConverter()
            )

        return self._word_converter

    @staticmethod
    def is_supported(
        path: str | Path,
    ) -> bool:

        return (
            Path(path)
            .suffix
            .lower()
            in SUPPORTED_EXTENSIONS
        )

    @staticmethod
    def default_output_path(
        input_path: str | Path,
        output_directory: str | Path,
    ) -> Path:

        input_path = Path(
            input_path
        )

        output_directory = Path(
            output_directory
        )

        extension = (
            input_path
            .suffix
            .lower()
        )

        if extension in WORD_EXTENSIONS:
            output_extension = ".pdf"

        else:
            output_extension = extension

        return (
            output_directory
            / (
                input_path.stem
                + "_REDACTED"
                + output_extension
            )
        )

    def sanitize_file(
        self,
        input_path: str | Path,
        output_path: str | Path,
    ):

        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        extension = (
            input_path
            .suffix
            .lower()
        )

        if extension in IMAGE_EXTENSIONS:
            return (
                self._get_image_sanitizer()
                .sanitize(
                    input_path,
                    output_path,
                )
            )

        if extension in PDF_EXTENSIONS:
            from bidr_sanitizer.pdf.sanitizer import (
                sanitize_pdf,
            )
    
            return sanitize_pdf(
                input_path,
                output_path,
                sanitizer=(
                    self._get_image_sanitizer()
                ),
            )

        if extension in WORD_EXTENSIONS:
            from bidr_sanitizer.word.sanitizer import (
                sanitize_word_document,
            )
            
            return sanitize_word_document(
                input_path,
                output_path,
                converter=(
                    self._get_word_converter()
                ),
                sanitizer=(
                    self._get_image_sanitizer()
                ),
            )

        if extension in TEXT_EXTENSIONS:
            from bidr_sanitizer.text.sanitizer import (
                sanitize_text_file,
            )
            
            return sanitize_text_file(
                input_path,
                output_path,
                semantic_recognizer=(
                    self._get_semantic_recognizer()
                ),
            )

        raise ValueError(
            "Unsupported file type: "
            f"{extension}"
        )

    def analyze_image_for_review(
        self,
        input_path: str | Path,
        *,
        settings: ImageSanitizerSettings | None = None,
    ) -> ImageReviewPlan:
        input_path = Path(input_path)
        extension = input_path.suffix.lower()

        if extension not in IMAGE_EXTENSIONS:
            raise ValueError(
                "Interactive review currently supports PNG and JPEG images; "
                f"received: {extension or '<none>'}"
            )

        return self._get_image_sanitizer().analyze_for_review(
            input_path,
            settings=settings,
        )

    def export_reviewed_image(
        self,
        input_path: str | Path,
        output_path: str | Path,
        plan: ImageReviewPlan,
    ) -> ReviewedImageExportResult:
        input_path = Path(input_path)
        output_path = Path(output_path)
        input_extension = input_path.suffix.lower()
        output_extension = output_path.suffix.lower()

        if input_extension not in IMAGE_EXTENSIONS:
            raise ValueError(
                "Interactive review currently supports PNG and JPEG images; "
                f"received: {input_extension or '<none>'}"
            )

        if output_extension not in IMAGE_EXTENSIONS:
            raise ValueError(
                "Reviewed image output must be PNG or JPEG; "
                f"received: {output_extension or '<none>'}"
            )

        return self._get_image_sanitizer().export_reviewed(
            input_path,
            output_path,
            plan,
        )

    def close(self) -> None:
        if self._image_sanitizer is None:
            return
        close = getattr(self._image_sanitizer, "close", None)
        if callable(close):
            close()
