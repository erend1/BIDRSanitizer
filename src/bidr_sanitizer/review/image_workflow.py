from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from PIL import Image

from bidr_sanitizer.models import BoundingBox, Detection
from bidr_sanitizer.ocr.base import OCRProvider
from bidr_sanitizer.pipeline import detect_image_pii
from bidr_sanitizer.recognizers.semantic.base import SemanticPIIRecognizer
from bidr_sanitizer.redaction import RedactionRegion, redact_image_file
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewAction,
    ReviewDecision,
    ReviewedImageExportResult,
    ReviewRegion,
    RegionProvenance,
)
from bidr_sanitizer.verification.verifier import verify_image
from bidr_sanitizer.vision.base import (
    FaceDetectorProvider,
    SignatureDetectorProvider,
)


IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})


class PlanRevisionConflictError(ValueError):
    """Raised when review changes target a stale plan revision."""


class PlanSourceMismatchError(ValueError):
    """Raised when a plan is applied to anything except its source image."""


def _source_sha256(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _image_identity(path: Path) -> tuple[str, int, int]:
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {path.suffix.lower()}")

    fingerprint = _source_sha256(path)

    with Image.open(path) as image:
        width, height = image.size
        image.verify()

    return fingerprint, width, height


def _assert_source_matches_plan(path: Path, plan: ImageReviewPlan) -> None:
    fingerprint, width, height = _image_identity(path)

    if (
        fingerprint != plan.source_sha256
        or width != plan.image_width
        or height != plan.image_height
    ):
        raise PlanSourceMismatchError(
            "The review plan does not match the selected source image."
        )


def analyze_image_for_review(
    input_path: str | Path,
    *,
    ocr: OCRProvider,
    settings: ImageSanitizerSettings | None = None,
    semantic_recognizer: SemanticPIIRecognizer | None = None,
    face_detector: FaceDetectorProvider | None = None,
    signature_detector: SignatureDetectorProvider | None = None,
) -> ImageReviewPlan:
    """Analyze an image and return a source-bound, geometry-only plan."""

    input_path = Path(input_path)
    settings = settings or ImageSanitizerSettings()
    identity_before = _image_identity(input_path)

    detections = detect_image_pii(
        input_path,
        ocr=ocr,
        semantic_recognizer=semantic_recognizer,
        face_detector=face_detector,
        signature_detector=signature_detector,
    )

    identity_after = _image_identity(input_path)
    if identity_after != identity_before:
        raise PlanSourceMismatchError("The source image changed during analysis.")

    fingerprint, width, height = identity_after
    regions = tuple(
        ReviewRegion(
            region_id=f"auto-{index:04d}",
            bbox=detection.bbox,
            provenance=RegionProvenance.AUTOMATIC,
            detection_type=detection.detection_type,
            confidence=detection.confidence,
        )
        for index, detection in enumerate(detections, start=1)
    )

    return ImageReviewPlan(
        plan_id=uuid4().hex,
        revision=0,
        source_sha256=fingerprint,
        image_width=width,
        image_height=height,
        settings=settings,
        regions=regions,
    )


def revise_image_review_plan(
    plan: ImageReviewPlan,
    *,
    expected_revision: int,
    decisions: Iterable[ReviewDecision] = (),
    manual_regions: Iterable[ManualRegionRequest] = (),
) -> ImageReviewPlan:
    """Return the next immutable plan revision after human review changes."""

    if expected_revision != plan.revision:
        raise PlanRevisionConflictError(
            f"Expected plan revision {expected_revision}, current revision is "
            f"{plan.revision}."
        )

    decision_items = tuple(decisions)
    decision_ids = [decision.region_id for decision in decision_items]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("A review region can have only one decision per revision.")

    known_ids = {region.region_id for region in plan.regions}
    unknown_ids = set(decision_ids) - known_ids
    if unknown_ids:
        raise ValueError("Review decision references an unknown region ID.")

    actions = {decision.region_id: decision.action for decision in decision_items}
    revised_regions = [
        replace(region, action=actions.get(region.region_id, region.action))
        for region in plan.regions
    ]

    for request in manual_regions:
        region_id = f"manual-{uuid4().hex}"
        revised_regions.append(
            ReviewRegion(
                region_id=region_id,
                bbox=request.bbox,
                provenance=RegionProvenance.MANUAL,
                detection_type=request.detection_type,
            )
        )

    return replace(
        plan,
        revision=plan.revision + 1,
        regions=tuple(revised_regions),
    )


def _detection_key(detection: Detection) -> tuple[object, int, int, int, int]:
    return (
        detection.detection_type,
        detection.bbox.x1,
        detection.bbox.y1,
        detection.bbox.x2,
        detection.bbox.y2,
    )


def _boxes_intersect(first: BoundingBox, second: BoundingBox) -> bool:
    return (
        first.x1 < second.x2
        and first.x2 > second.x1
        and first.y1 < second.y2
        and first.y2 > second.y1
    )


def _is_blocked_by_automatic_removal(
    detection: Detection,
    plan: ImageReviewPlan,
) -> bool:
    for removed in plan.removed_automatic_regions:
        if detection.detection_type is not removed.detection_type:
            continue

        override_scope = removed.bbox.expand(
            margin=plan.settings.redaction_margin,
            image_width=plan.image_width,
            image_height=plan.image_height,
        )
        if _boxes_intersect(detection.bbox, override_scope):
            return True

    return False


def export_reviewed_image(
    input_path: str | Path,
    output_path: str | Path,
    plan: ImageReviewPlan,
    *,
    ocr: OCRProvider,
    semantic_recognizer: SemanticPIIRecognizer | None = None,
    face_detector: FaceDetectorProvider | None = None,
    signature_detector: SignatureDetectorProvider | None = None,
) -> ReviewedImageExportResult:
    """Destructively redact a reviewed plan and verify the exported pixels."""

    input_path = Path(input_path)
    output_path = Path(output_path)

    paths_are_same = input_path.resolve() == output_path.resolve()
    if input_path.exists() and output_path.exists():
        paths_are_same = paths_are_same or os.path.samefile(input_path, output_path)

    if paths_are_same:
        raise ValueError("Input and output paths must be different.")

    if output_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported output image type: {output_path.suffix.lower()}")

    _assert_source_matches_plan(input_path, plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".bidr_review_",
        suffix=output_path.suffix,
        dir=output_path.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)

    applied_plan_regions = plan.active_regions
    remediation_detections: list[Detection] = []
    redaction_regions: list[RedactionRegion] = list(applied_plan_regions)
    redaction_passes = 1

    try:
        redact_image_file(
            input_path,
            temporary_path,
            redaction_regions,
            margin=plan.settings.redaction_margin,
        )

        verification = verify_image(
            temporary_path,
            ocr=ocr,
            semantic_recognizer=semantic_recognizer,
            face_detector=face_detector,
            signature_detector=signature_detector,
        )

        while (
            not verification.passed
            and redaction_passes < plan.settings.max_redaction_passes
        ):
            existing_keys = {
                _detection_key(detection) for detection in remediation_detections
            }
            existing_keys.update(
                _detection_key(
                    Detection(
                        detection_type=region.detection_type,
                        bbox=region.bbox,
                        confidence=region.confidence,
                    )
                )
                for region in applied_plan_regions
                if region.detection_type is not None and region.confidence is not None
            )

            newly_found: list[Detection] = []
            for detection in verification.remaining_detections:
                key = _detection_key(detection)
                if key in existing_keys:
                    continue

                if _is_blocked_by_automatic_removal(detection, plan):
                    continue

                existing_keys.add(key)
                newly_found.append(detection)

            if not newly_found:
                break

            remediation_detections.extend(newly_found)
            redaction_regions.extend(newly_found)
            redact_image_file(
                input_path,
                temporary_path,
                redaction_regions,
                margin=plan.settings.redaction_margin,
            )
            redaction_passes += 1

            verification = verify_image(
                temporary_path,
                ocr=ocr,
                semantic_recognizer=semantic_recognizer,
                face_detector=face_detector,
                signature_detector=signature_detector,
            )

        # Detect a source replacement that occurred after the initial check and
        # never promote an output assembled from changing source bytes.
        _assert_source_matches_plan(input_path, plan)
        os.replace(temporary_path, output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise

    return ReviewedImageExportResult(
        output_path=output_path,
        plan_id=plan.plan_id,
        plan_revision=plan.revision,
        applied_plan_regions=applied_plan_regions,
        remediation_detections=tuple(remediation_detections),
        verification=verification,
        redaction_passes=redaction_passes,
        automatic_removal_count=plan.automatic_removal_count,
        manual_addition_count=plan.manual_addition_count,
    )
