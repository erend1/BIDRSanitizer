from pathlib import Path

import pytest

from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ReviewAction,
    ReviewedImageExportResult,
    ReviewedOutputStatus,
    ReviewRegion,
    RegionProvenance,
)
from bidr_sanitizer.verification.models import VerificationReport


def _automatic_region(*, region_id: str = "auto-0001") -> ReviewRegion:
    return ReviewRegion(
        region_id=region_id,
        bbox=BoundingBox(10, 10, 30, 30),
        provenance=RegionProvenance.AUTOMATIC,
        detection_type=DetectionType.FACE,
        confidence=0.9,
    )


def test_image_sanitizer_settings_validate_safety_bounds():
    with pytest.raises(ValueError, match="cannot be negative"):
        ImageSanitizerSettings(redaction_margin=-1)

    with pytest.raises(ValueError, match="at least 1"):
        ImageSanitizerSettings(max_redaction_passes=0)


def test_automatic_review_region_requires_detector_metadata():
    with pytest.raises(ValueError, match="detection type and confidence"):
        ReviewRegion(
            region_id="auto-0001",
            bbox=BoundingBox(10, 10, 30, 30),
            provenance=RegionProvenance.AUTOMATIC,
        )


def test_manual_review_region_rejects_detector_confidence():
    with pytest.raises(ValueError, match="cannot have detector confidence"):
        ReviewRegion(
            region_id="manual-1",
            bbox=BoundingBox(10, 10, 30, 30),
            provenance=RegionProvenance.MANUAL,
            confidence=0.8,
        )


def test_review_plan_is_immutable_and_hides_source_fingerprint_from_repr():
    fingerprint = "a" * 64
    supplied_regions = [_automatic_region()]
    plan = ImageReviewPlan(
        plan_id="plan-1",
        revision=0,
        source_sha256=fingerprint,
        image_width=100,
        image_height=80,
        settings=ImageSanitizerSettings(),
        regions=supplied_regions,  # type: ignore[arg-type]
    )

    supplied_regions.clear()

    assert len(plan.regions) == 1
    assert fingerprint not in repr(plan)


def test_review_plan_rejects_duplicate_ids_and_out_of_bounds_regions():
    with pytest.raises(ValueError, match="must be unique"):
        ImageReviewPlan(
            plan_id="plan-1",
            revision=0,
            source_sha256="a" * 64,
            image_width=100,
            image_height=100,
            settings=ImageSanitizerSettings(),
            regions=(_automatic_region(), _automatic_region()),
        )

    outside = ReviewRegion(
        region_id="manual-1",
        bbox=BoundingBox(90, 90, 110, 110),
        provenance=RegionProvenance.MANUAL,
    )
    with pytest.raises(ValueError, match="exceeds image dimensions"):
        ImageReviewPlan(
            plan_id="plan-1",
            revision=0,
            source_sha256="a" * 64,
            image_width=100,
            image_height=100,
            settings=ImageSanitizerSettings(),
            regions=(outside,),
        )


@pytest.mark.parametrize(
    ("remaining_count", "automatic_removals", "expected_status", "passed"),
    [
        (0, 0, ReviewedOutputStatus.PASSED, True),
        (
            0,
            1,
            ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES,
            False,
        ),
        (1, 0, ReviewedOutputStatus.REVIEW_REQUIRED, False),
    ],
)
def test_reviewed_output_status_is_conservative(
    remaining_count,
    automatic_removals,
    expected_status,
    passed,
):
    remaining = tuple(
        # The value is synthetic and contains no source text.
        Detection(
            detection_type=DetectionType.FACE,
            bbox=BoundingBox(10 + index, 10, 30 + index, 30),
        )
        for index in range(remaining_count)
    )
    result = ReviewedImageExportResult(
        output_path=Path("out.png"),
        plan_id="plan-1",
        plan_revision=0,
        applied_plan_regions=(),
        remediation_detections=(),
        verification=VerificationReport(remaining_detections=remaining),
        redaction_passes=1,
        automatic_removal_count=automatic_removals,
        manual_addition_count=0,
    )

    assert result.status is expected_status
    assert result.passed is passed
    assert result.detectors_clear is (remaining_count == 0)
