from __future__ import annotations

import shutil
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.pdfgen.canvas import (
    Canvas,
)

from bidr_sanitizer.pdf.sanitizer import (
    pdf_has_extractable_text,
    sanitize_pdf,
)
from bidr_sanitizer.pipeline import (
    SanitizationResult,
)
from bidr_sanitizer.verification.models import (
    VerificationReport,
)


class PassthroughImageSanitizer:
    """
    Fake image sanitizer for testing PDF plumbing.

    It does NOT perform privacy detection.
    """

    def sanitize(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        margin: int = 5,
        max_redaction_passes: int = 3,
    ) -> SanitizationResult:

        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        shutil.copyfile(
            input_path,
            output_path,
        )

        return SanitizationResult(
            output_path=output_path,
            applied_detections=(),
            verification=(
                VerificationReport(
                    remaining_detections=()
                )
            ),
            redaction_passes=1,
        )


def _create_two_page_test_pdf(
    path: Path,
) -> None:

    canvas = Canvas(
        str(path),
        pagesize=(
            595,
            842,
        ),
    )

    canvas.drawString(
        72,
        750,
        "Page one test content",
    )

    canvas.showPage()

    # Deliberately use a different page shape.
    canvas.setPageSize(
        (
            842,
            595,
        )
    )

    canvas.drawString(
        72,
        500,
        "Page two test content",
    )

    canvas.showPage()

    canvas.save()


def test_pdf_is_rebuilt_as_image_only(
    tmp_path,
):
    input_path = (
        tmp_path
        / "input.pdf"
    )

    output_path = (
        tmp_path
        / "output.pdf"
    )

    _create_two_page_test_pdf(
        input_path
    )

    result = sanitize_pdf(
        input_path,
        output_path,
        sanitizer=(
            PassthroughImageSanitizer()
        ),
        dpi=150,
    )

    assert output_path.exists()

    assert result.passed

    assert result.page_count == 2

    assert result.text_layer_empty

    assert not pdf_has_extractable_text(
        output_path
    )


def test_pdf_page_count_is_preserved(
    tmp_path,
):
    input_path = (
        tmp_path
        / "input.pdf"
    )

    output_path = (
        tmp_path
        / "output.pdf"
    )

    _create_two_page_test_pdf(
        input_path
    )

    sanitize_pdf(
        input_path,
        output_path,
        sanitizer=(
            PassthroughImageSanitizer()
        ),
        dpi=150,
    )

    output_pdf = (
        pdfium.PdfDocument(
            str(output_path)
        )
    )

    try:
        assert len(
            output_pdf
        ) == 2

    finally:
        output_pdf.close()