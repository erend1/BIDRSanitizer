from collections import deque
from pathlib import Path

from PIL import Image
import pytest

from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.ocr.models import OCRTextItem
from bidr_sanitizer.review import (
    ImageSanitizerSettings,
    ManualRegionRequest,
    PlanRevisionConflictError,
    PlanSourceMismatchError,
    ReviewAction,
    ReviewDecision,
    ReviewGeometryUpdate,
    ReviewedOutputStatus,
    RegionProvenance,
    analyze_image_for_review,
    export_reviewed_image,
    revise_image_review_plan,
)


class SequentialOCR:
    def __init__(self, responses: list[list[OCRTextItem]]) -> None:
        self._responses = deque(responses)

    def recognize(self, image_path: str | Path) -> list[OCRTextItem]:
        if not self._responses:
            raise RuntimeError("Unexpected OCR call.")
        return self._responses.popleft()


class SequentialDetector:
    def __init__(self, responses: list[list[Detection]]) -> None:
        self._responses = deque(responses)

    def detect(self, image_path: str | Path) -> list[Detection]:
        if not self._responses:
            raise RuntimeError("Unexpected detector call.")
        return self._responses.popleft()


class FailingOCR:
    def recognize(self, image_path: str | Path) -> list[OCRTextItem]:
        raise RuntimeError("Synthetic verifier failure.")


def _white_image(path: Path, size: tuple[int, int] = (100, 100)) -> None:
    Image.new("RGB", size, color="white").save(path)


def _detection(
    detection_type: DetectionType,
    coordinates: tuple[int, int, int, int],
) -> Detection:
    return Detection(
        detection_type=detection_type,
        bbox=BoundingBox(*coordinates),
        confidence=0.9,
    )


def test_analysis_combines_configured_detectors_without_retaining_ocr_text(tmp_path):
    input_path = tmp_path / "source.png"
    _white_image(input_path)

    ocr_item = OCRTextItem(
        text="Telefon: 0532 123 45 67",
        bbox=BoundingBox(5, 5, 35, 15),
        confidence=0.98,
    )
    face = _detection(DetectionType.FACE, (40, 10, 60, 30))
    signature = _detection(DetectionType.SIGNATURE, (20, 60, 70, 75))

    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[ocr_item]]),
        face_detector=SequentialDetector([[face]]),
        signature_detector=SequentialDetector([[signature]]),
    )

    assert plan.revision == 0
    assert (plan.image_width, plan.image_height) == (100, 100)
    assert [region.region_id for region in plan.regions] == [
        "auto-0001",
        "auto-0002",
        "auto-0003",
    ]
    assert [region.detection_type for region in plan.regions] == [
        DetectionType.PHONE,
        DetectionType.FACE,
        DetectionType.SIGNATURE,
    ]
    assert "0532" not in repr(plan)


def test_revision_records_automatic_removal_and_manual_addition(tmp_path):
    input_path = tmp_path / "source.png"
    _white_image(input_path)
    face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
        settings=ImageSanitizerSettings(redaction_margin=0),
    )

    revised = revise_image_review_plan(
        plan,
        expected_revision=0,
        decisions=[ReviewDecision("auto-0001", ReviewAction.REMOVE)],
        manual_regions=[ManualRegionRequest(BoundingBox(40, 40, 55, 55))],
    )

    assert plan.revision == 0
    assert plan.regions[0].action is ReviewAction.RETAIN
    assert revised.revision == 1
    assert revised.regions[0].action is ReviewAction.REMOVE
    assert revised.regions[1].region_id.startswith("manual-")
    assert revised.regions[1].provenance is RegionProvenance.MANUAL
    assert revised.automatic_removal_count == 1
    assert revised.manual_addition_count == 1


def test_revision_rejects_stale_duplicate_and_unknown_decisions(tmp_path):
    input_path = tmp_path / "source.png"
    _white_image(input_path)
    face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
    )

    with pytest.raises(PlanRevisionConflictError):
        revise_image_review_plan(plan, expected_revision=1)

    with pytest.raises(ValueError, match="only one decision"):
        revise_image_review_plan(
            plan,
            expected_revision=0,
            decisions=[
                ReviewDecision("auto-0001", ReviewAction.REMOVE),
                ReviewDecision("auto-0001", ReviewAction.RETAIN),
            ],
        )

    with pytest.raises(ValueError, match="unknown region"):
        revise_image_review_plan(
            plan,
            expected_revision=0,
            decisions=[ReviewDecision("auto-9999", ReviewAction.REMOVE)],
        )


def test_automatic_geometry_update_is_revisioned_and_conservative(tmp_path):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)
    face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
        settings=ImageSanitizerSettings(redaction_margin=0),
    )

    revised = revise_image_review_plan(
        plan,
        expected_revision=0,
        geometry_updates=[
            ReviewGeometryUpdate("auto-0001", BoundingBox(15, 15, 40, 40))
        ],
    )
    assert revised.revision == 1
    assert revised.regions[0].bbox == BoundingBox(15, 15, 40, 40)
    assert revised.regions[0].geometry_modified
    assert revised.automatic_geometry_adjustment_count == 1

    result = export_reviewed_image(
        input_path,
        output_path,
        revised,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[]]),
    )
    assert result.detectors_clear
    assert result.status is ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES
    assert result.automatic_geometry_adjustment_count == 1


def test_reviewed_export_applies_retained_and_manual_regions_but_not_removal(
    tmp_path,
):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)

    face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    signature = _detection(DetectionType.SIGNATURE, (60, 60, 80, 80))
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
        signature_detector=SequentialDetector([[signature]]),
        settings=ImageSanitizerSettings(redaction_margin=0),
    )
    plan = revise_image_review_plan(
        plan,
        expected_revision=0,
        decisions=[ReviewDecision("auto-0001", ReviewAction.REMOVE)],
        manual_regions=[ManualRegionRequest(BoundingBox(40, 40, 50, 50))],
    )

    result = export_reviewed_image(
        input_path,
        output_path,
        plan,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[]]),
        signature_detector=SequentialDetector([[]]),
    )

    with Image.open(output_path) as output:
        assert output.getpixel((20, 20)) == (255, 255, 255)
        assert output.getpixel((45, 45)) == (0, 0, 0)
        assert output.getpixel((70, 70)) == (0, 0, 0)

    assert result.detectors_clear
    assert not result.passed
    assert result.status is ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES
    assert result.automatic_removal_count == 1
    assert result.manual_addition_count == 1


def test_verifier_cannot_silently_readd_an_explicitly_removed_region(tmp_path):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)
    face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
        settings=ImageSanitizerSettings(redaction_margin=0),
    )
    plan = revise_image_review_plan(
        plan,
        expected_revision=0,
        decisions=[ReviewDecision("auto-0001", ReviewAction.REMOVE)],
    )

    result = export_reviewed_image(
        input_path,
        output_path,
        plan,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[face]]),
    )

    with Image.open(output_path) as output:
        assert output.getpixel((20, 20)) == (255, 255, 255)

    assert result.status is ReviewedOutputStatus.REVIEW_REQUIRED
    assert not result.detectors_clear
    assert result.remediation_detections == ()
    assert result.redaction_passes == 1


def test_reviewed_export_remediates_new_detection_from_original_pixels(tmp_path):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)
    original_face = _detection(DetectionType.FACE, (10, 10, 30, 30))
    newly_found_signature = _detection(
        DetectionType.SIGNATURE,
        (55, 55, 75, 70),
    )
    plan = analyze_image_for_review(
        input_path,
        ocr=SequentialOCR([[]]),
        face_detector=SequentialDetector([[original_face]]),
        settings=ImageSanitizerSettings(redaction_margin=0),
    )

    result = export_reviewed_image(
        input_path,
        output_path,
        plan,
        ocr=SequentialOCR([[], []]),
        face_detector=SequentialDetector([[], []]),
        signature_detector=SequentialDetector([[newly_found_signature], []]),
    )

    with Image.open(output_path) as output:
        assert output.getpixel((20, 20)) == (0, 0, 0)
        assert output.getpixel((60, 60)) == (0, 0, 0)

    assert result.status is ReviewedOutputStatus.PASSED
    assert result.passed
    assert result.redaction_passes == 2
    assert result.remediation_detections == (newly_found_signature,)


def test_export_rejects_a_changed_source_before_writing_output(tmp_path):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)
    plan = analyze_image_for_review(input_path, ocr=SequentialOCR([[]]))

    Image.new("RGB", (100, 100), color="blue").save(input_path)

    with pytest.raises(PlanSourceMismatchError):
        export_reviewed_image(
            input_path,
            output_path,
            plan,
            ocr=SequentialOCR([[]]),
        )

    assert not output_path.exists()


def test_verifier_failure_does_not_replace_an_existing_destination(tmp_path):
    input_path = tmp_path / "source.png"
    output_path = tmp_path / "reviewed.png"
    _white_image(input_path)
    Image.new("RGB", (100, 100), color="green").save(output_path)
    plan = analyze_image_for_review(input_path, ocr=SequentialOCR([[]]))

    with pytest.raises(RuntimeError, match="Synthetic verifier failure"):
        export_reviewed_image(
            input_path,
            output_path,
            plan,
            ocr=FailingOCR(),
        )

    with Image.open(output_path) as output:
        assert output.getpixel((50, 50)) == (0, 128, 0)

    assert list(tmp_path.glob(".bidr_review_*.png")) == []
