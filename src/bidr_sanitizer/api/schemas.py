from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bidr_sanitizer.api.sessions import ReviewSessionSnapshot, ReviewSessionState
from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewAction,
    ReviewDecision,
    ReviewedImageExportResult,
    ReviewedOutputStatus,
    ReviewRegion,
    RegionProvenance,
)


StrictNonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
StrictPositiveInt = Annotated[int, Field(ge=1, strict=True)]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundingBoxSchema(APIModel):
    x1: StrictNonNegativeInt
    y1: StrictNonNegativeInt
    x2: StrictPositiveInt
    y2: StrictPositiveInt

    @model_validator(mode="after")
    def validate_coordinate_order(self) -> BoundingBoxSchema:
        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1.")
        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1.")
        return self

    def to_domain(self) -> BoundingBox:
        return BoundingBox(self.x1, self.y1, self.x2, self.y2)

    @classmethod
    def from_domain(cls, bbox: BoundingBox) -> BoundingBoxSchema:
        return cls(x1=bbox.x1, y1=bbox.y1, x2=bbox.x2, y2=bbox.y2)


class ImageSettingsSchema(APIModel):
    redaction_margin: StrictNonNegativeInt = 5
    max_redaction_passes: StrictPositiveInt = 3

    def to_domain(self) -> ImageSanitizerSettings:
        return ImageSanitizerSettings(
            redaction_margin=self.redaction_margin,
            max_redaction_passes=self.max_redaction_passes,
        )

    @classmethod
    def from_domain(cls, settings: ImageSanitizerSettings) -> ImageSettingsSchema:
        return cls(
            redaction_margin=settings.redaction_margin,
            max_redaction_passes=settings.max_redaction_passes,
        )


class ReviewDecisionSchema(APIModel):
    region_id: str = Field(min_length=1, max_length=100)
    action: ReviewAction

    def to_domain(self) -> ReviewDecision:
        return ReviewDecision(region_id=self.region_id, action=self.action)


class ManualRegionSchema(APIModel):
    bbox: BoundingBoxSchema
    detection_type: DetectionType | None = None

    def to_domain(self) -> ManualRegionRequest:
        return ManualRegionRequest(
            bbox=self.bbox.to_domain(),
            detection_type=self.detection_type,
        )


class RevisePlanRequest(APIModel):
    expected_revision: StrictNonNegativeInt
    decisions: list[ReviewDecisionSchema] = Field(default_factory=list, max_length=10_000)
    manual_regions: list[ManualRegionSchema] = Field(
        default_factory=list,
        max_length=10_000,
    )


class ExportRequest(APIModel):
    expected_revision: StrictNonNegativeInt


class ReviewRegionSchema(APIModel):
    region_id: str
    bbox: BoundingBoxSchema
    provenance: RegionProvenance
    action: ReviewAction
    detection_type: DetectionType | None
    confidence: float | None

    @classmethod
    def from_domain(cls, region: ReviewRegion) -> ReviewRegionSchema:
        return cls(
            region_id=region.region_id,
            bbox=BoundingBoxSchema.from_domain(region.bbox),
            provenance=region.provenance,
            action=region.action,
            detection_type=region.detection_type,
            confidence=region.confidence,
        )


class DetectionSchema(APIModel):
    detection_type: DetectionType
    bbox: BoundingBoxSchema
    confidence: float

    @classmethod
    def from_domain(cls, detection: Detection) -> DetectionSchema:
        return cls(
            detection_type=detection.detection_type,
            bbox=BoundingBoxSchema.from_domain(detection.bbox),
            confidence=detection.confidence,
        )


class ReviewPlanSchema(APIModel):
    plan_id: str
    revision: int
    image_width: int
    image_height: int
    settings: ImageSettingsSchema
    regions: list[ReviewRegionSchema]

    @classmethod
    def from_domain(cls, plan: ImageReviewPlan) -> ReviewPlanSchema:
        return cls(
            plan_id=plan.plan_id,
            revision=plan.revision,
            image_width=plan.image_width,
            image_height=plan.image_height,
            settings=ImageSettingsSchema.from_domain(plan.settings),
            regions=[ReviewRegionSchema.from_domain(region) for region in plan.regions],
        )


class ReviewedExportSchema(APIModel):
    status: ReviewedOutputStatus
    detectors_clear: bool
    passed: bool
    plan_revision: int
    redaction_passes: int
    automatic_removal_count: int
    manual_addition_count: int
    applied_region_count: int
    remaining_detections: list[DetectionSchema]
    remediation_detections: list[DetectionSchema]

    @classmethod
    def from_domain(
        cls,
        result: ReviewedImageExportResult,
    ) -> ReviewedExportSchema:
        return cls(
            status=result.status,
            detectors_clear=result.detectors_clear,
            passed=result.passed,
            plan_revision=result.plan_revision,
            redaction_passes=result.redaction_passes,
            automatic_removal_count=result.automatic_removal_count,
            manual_addition_count=result.manual_addition_count,
            applied_region_count=len(result.applied_plan_regions),
            remaining_detections=[
                DetectionSchema.from_domain(detection)
                for detection in result.verification.remaining_detections
            ],
            remediation_detections=[
                DetectionSchema.from_domain(detection)
                for detection in result.remediation_detections
            ],
        )


class ReviewSessionSchema(APIModel):
    session_id: str
    state: ReviewSessionState
    media_type: str
    image_width: int
    image_height: int
    plan: ReviewPlanSchema | None
    export: ReviewedExportSchema | None

    @classmethod
    def from_snapshot(cls, snapshot: ReviewSessionSnapshot) -> ReviewSessionSchema:
        return cls(
            session_id=snapshot.session_id,
            state=snapshot.state,
            media_type=snapshot.media_type,
            image_width=snapshot.image_width,
            image_height=snapshot.image_height,
            plan=(
                ReviewPlanSchema.from_domain(snapshot.plan)
                if snapshot.plan is not None
                else None
            ),
            export=(
                ReviewedExportSchema.from_domain(snapshot.export_result)
                if snapshot.export_result is not None
                else None
            ),
        )


class HealthSchema(APIModel):
    status: str
    api_version: str
