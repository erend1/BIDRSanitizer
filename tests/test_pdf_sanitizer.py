from __future__ import annotations

import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from reportlab.pdfgen.canvas import (
    Canvas,
)

from bidr_sanitizer.pdf.sanitizer import (
    PDF_MAX_MEAN_CHANNEL_RMS,
    _build_image_only_pdf,
    _mean_channel_rms,
    compact_redacted_pdf_page,
    pdf_has_extractable_text,
    sanitize_pdf,
)
from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.pipeline import (
    SanitizationResult,
)
from bidr_sanitizer.verification.models import (
    VerificationReport,
)
from bidr_sanitizer.redaction import redact_image_file


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
        output_transform=None,
    ) -> SanitizationResult:

        input_path = Path(
            input_path
        )

        output_path = Path(
            output_path
        )

        if output_transform is None:
            shutil.copyfile(
                input_path,
                output_path,
            )
        else:
            redact_image_file(
                input_path,
                output_path,
                (),
                margin=margin,
                output_transform=output_transform,
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


def test_compact_pdf_page_preserves_resolution_and_exact_black_redaction():
    image = Image.new("RGB", (320, 200), color=(248, 248, 248))
    draw = ImageDraw.Draw(image)
    for offset in range(20, 180, 20):
        draw.line((10, offset, 310, offset), fill=(offset, 40, 180), width=2)

    detection = Detection(
        detection_type=DetectionType.PERSON,
        bbox=BoundingBox(100, 60, 180, 100),
        confidence=0.99,
    )
    compact = compact_redacted_pdf_page(image, (detection,), 3)

    assert compact.size == image.size
    assert compact.mode == "P"

    rgb = compact.convert("RGB")
    redacted = rgb.crop((97, 57, 184, 104))
    assert redacted.getextrema() == ((0, 0), (0, 0), (0, 0))


def test_compact_pdf_page_bounds_color_error_without_downsampling():
    image = Image.new("RGB", (256, 128), color=(250, 250, 248))
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 20, 240, 45), fill=(28, 80, 160))
    draw.text((20, 70), "Sharp synthetic document text", fill=(15, 15, 15))

    compact = compact_redacted_pdf_page(image, (), 0)

    assert compact.size == image.size
    assert _mean_channel_rms(image, compact.convert("RGB")) <= (
        PDF_MAX_MEAN_CHANNEL_RMS
    )


def test_image_only_pdf_directly_embeds_compact_png_streams(tmp_path):
    page_paths = []
    total_image_bytes = 0
    for page_number, page_size in enumerate(((120, 180), (180, 120)), start=1):
        image = Image.new("RGB", page_size, color=(250, 250, 250))
        ImageDraw.Draw(image).text((10, 10), f"Synthetic {page_number}", fill="black")
        compact = compact_redacted_pdf_page(image, (), 0)
        page_path = tmp_path / f"page_{page_number}.png"
        compact.save(page_path, format="PNG", optimize=True)
        total_image_bytes += page_path.stat().st_size
        page_paths.append((page_path, float(page_size[0]), float(page_size[1])))

    output_path = tmp_path / "direct.pdf"
    _build_image_only_pdf(page_paths, output_path)

    assert output_path.stat().st_size <= total_image_bytes + 10_000
    assert not pdf_has_extractable_text(output_path)

    document = pdfium.PdfDocument(str(output_path))
    try:
        assert len(document) == 2
        assert tuple(round(value) for value in document[0].get_size()) == (120, 180)
        assert tuple(round(value) for value in document[1].get_size()) == (180, 120)
    finally:
        document.close()


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
