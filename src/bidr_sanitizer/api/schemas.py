from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bidr_sanitizer.api.sessions import (
    ReviewPageSnapshot,
    ReviewSessionSnapshot,
    ReviewSessionState,
    ReviewedDocumentExportResult,
)
from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.review.models import (
    ImageReviewPlan,
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewAction,
    ReviewDecision,
    ReviewGeometryUpdate,
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


class ReviewGeometryUpdateSchema(APIModel):
    region_id: str = Field(min_length=1, max_length=100)
    bbox: BoundingBoxSchema

    def to_domain(self) -> ReviewGeometryUpdate:
        return ReviewGeometryUpdate(
            region_id=self.region_id,
            bbox=self.bbox.to_domain(),
        )


class ManualRegionSchema(APIModel):
    bbox: BoundingBoxSchema
    detection_type: DetectionType | None = None

    def to_domain(self) -> ManualRegionRequest:
        return ManualRegionRequest(
            bbox=self.bbox.to_domain(),
            detection_type=self.detection_type,
        )


class RevisePlanRequest(APIModel):
    page_number: StrictPositiveInt = 1
    expected_revision: StrictNonNegativeInt
    decisions: list[ReviewDecisionSchema] = Field(default_factory=list, max_length=10_000)
    geometry_updates: list[ReviewGeometryUpdateSchema] = Field(
        default_factory=list,
        max_length=10_000,
    )
    manual_regions: list[ManualRegionSchema] = Field(
        default_factory=list,
        max_length=10_000,
    )


class PageRevisionSchema(APIModel):
    page_number: StrictPositiveInt
    revision: StrictNonNegativeInt


class ExportRequest(APIModel):
    expected_revision: StrictNonNegativeInt | None = None
    expected_revisions: list[PageRevisionSchema] = Field(
        default_factory=list,
        max_length=1_000,
    )

    @model_validator(mode="after")
    def validate_revision_shape(self) -> ExportRequest:
        if self.expected_revision is None and not self.expected_revisions:
            raise ValueError("At least one expected revision is required.")
        if self.expected_revision is not None and self.expected_revisions:
            raise ValueError("Use either expected_revision or expected_revisions.")

        page_numbers = [item.page_number for item in self.expected_revisions]
        if len(page_numbers) != len(set(page_numbers)):
            raise ValueError("Page revisions must have unique page numbers.")
        return self

    def to_revision_map(self) -> dict[int, int]:
        if self.expected_revision is not None:
            return {1: self.expected_revision}
        return {
            item.page_number: item.revision for item in self.expected_revisions
        }


class ReviewRegionSchema(APIModel):
    region_id: str
    bbox: BoundingBoxSchema
    provenance: RegionProvenance
    action: ReviewAction
    detection_type: DetectionType | None
    confidence: float | None
    geometry_modified: bool

    @classmethod
    def from_domain(cls, region: ReviewRegion) -> ReviewRegionSchema:
        return cls(
            region_id=region.region_id,
            bbox=BoundingBoxSchema.from_domain(region.bbox),
            provenance=region.provenance,
            action=region.action,
            detection_type=region.detection_type,
            confidence=region.confidence,
            geometry_modified=region.geometry_modified,
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
    automatic_geometry_adjustment_count: int
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
            automatic_geometry_adjustment_count=(
                result.automatic_geometry_adjustment_count
            ),
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


class ReviewPageSchema(APIModel):
    page_number: int
    image_width: int
    image_height: int
    plan: ReviewPlanSchema | None
    export: ReviewedExportSchema | None

    @classmethod
    def from_snapshot(cls, page: ReviewPageSnapshot) -> ReviewPageSchema:
        return cls(
            page_number=page.page_number,
            image_width=page.image_width,
            image_height=page.image_height,
            plan=(
                ReviewPlanSchema.from_domain(page.plan)
                if page.plan is not None
                else None
            ),
            export=(
                ReviewedExportSchema.from_domain(page.export_result)
                if page.export_result is not None
                else None
            ),
        )


class PageDetectionSchema(DetectionSchema):
    page_number: int


class DocumentReviewedExportSchema(APIModel):
    status: ReviewedOutputStatus
    detectors_clear: bool
    passed: bool
    text_layer_empty: bool | None
    page_count: int
    pages: list[ReviewedExportSchema]
    page_revisions: list[PageRevisionSchema]
    plan_revision: int
    redaction_passes: int
    automatic_removal_count: int
    automatic_geometry_adjustment_count: int
    manual_addition_count: int
    applied_region_count: int
    remaining_detections: list[PageDetectionSchema]
    remediation_detections: list[PageDetectionSchema]

    @classmethod
    def from_domain(
        cls,
        result: ReviewedDocumentExportResult,
    ) -> DocumentReviewedExportSchema:
        page_exports = [
            ReviewedExportSchema.from_domain(page) for page in result.pages
        ]
        page_revisions = [
            PageRevisionSchema(page_number=index, revision=page.plan_revision)
            for index, page in enumerate(result.pages, start=1)
        ]
        remaining = [
            PageDetectionSchema(
                page_number=page_number,
                detection_type=detection.detection_type,
                bbox=BoundingBoxSchema.from_domain(detection.bbox),
                confidence=detection.confidence,
            )
            for page_number, page in enumerate(result.pages, start=1)
            for detection in page.verification.remaining_detections
        ]
        remediation = [
            PageDetectionSchema(
                page_number=page_number,
                detection_type=detection.detection_type,
                bbox=BoundingBoxSchema.from_domain(detection.bbox),
                confidence=detection.confidence,
            )
            for page_number, page in enumerate(result.pages, start=1)
            for detection in page.remediation_detections
        ]
        return cls(
            status=result.status,
            detectors_clear=result.detectors_clear,
            passed=result.passed,
            text_layer_empty=result.text_layer_empty,
            page_count=len(result.pages),
            pages=page_exports,
            page_revisions=page_revisions,
            plan_revision=max((page.plan_revision for page in result.pages), default=0),
            redaction_passes=sum(page.redaction_passes for page in result.pages),
            automatic_removal_count=sum(
                page.automatic_removal_count for page in result.pages
            ),
            automatic_geometry_adjustment_count=sum(
                page.automatic_geometry_adjustment_count for page in result.pages
            ),
            manual_addition_count=sum(
                page.manual_addition_count for page in result.pages
            ),
            applied_region_count=sum(
                len(page.applied_plan_regions) for page in result.pages
            ),
            remaining_detections=remaining,
            remediation_detections=remediation,
        )


class ReviewSessionSchema(APIModel):
    session_id: str
    state: ReviewSessionState
    media_type: str
    page_count: int
    pages: list[ReviewPageSchema]
    image_width: int
    image_height: int
    plan: ReviewPlanSchema | None
    export: DocumentReviewedExportSchema | None

    @classmethod
    def from_snapshot(cls, snapshot: ReviewSessionSnapshot) -> ReviewSessionSchema:
        return cls(
            session_id=snapshot.session_id,
            state=snapshot.state,
            media_type=snapshot.media_type,
            page_count=snapshot.page_count,
            pages=[ReviewPageSchema.from_snapshot(page) for page in snapshot.pages],
            image_width=snapshot.image_width,
            image_height=snapshot.image_height,
            plan=(
                ReviewPlanSchema.from_domain(snapshot.plan)
                if snapshot.plan is not None
                else None
            ),
            export=(
                DocumentReviewedExportSchema.from_domain(snapshot.export_result)
                if snapshot.export_result is not None
                else None
            ),
        )


class HealthSchema(APIModel):
    status: str
    api_version: str
