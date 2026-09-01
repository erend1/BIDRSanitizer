from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import string

from bidr_sanitizer.models import BoundingBox, Detection, DetectionType
from bidr_sanitizer.verification.models import VerificationReport


class RegionProvenance(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


class ReviewAction(str, Enum):
    RETAIN = "retain"
    REMOVE = "remove"


class ReviewedOutputStatus(str, Enum):
    PASSED = "passed"
    VERIFIED_WITH_HUMAN_OVERRIDES = "verified_with_human_overrides"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class ImageSanitizerSettings:
    """Settings that currently affect deterministic image export."""

    redaction_margin: int = 5
    max_redaction_passes: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.redaction_margin, int) or isinstance(
            self.redaction_margin, bool
        ):
            raise TypeError("redaction_margin must be an integer.")

        if not isinstance(self.max_redaction_passes, int) or isinstance(
            self.max_redaction_passes, bool
        ):
            raise TypeError("max_redaction_passes must be an integer.")

        if self.redaction_margin < 0:
            raise ValueError("redaction_margin cannot be negative.")

        if self.max_redaction_passes < 1:
            raise ValueError("max_redaction_passes must be at least 1.")


@dataclass(frozen=True, slots=True)
class ReviewRegion:
    """A geometry-only region proposed for deterministic redaction."""

    region_id: str
    bbox: BoundingBox
    provenance: RegionProvenance
    action: ReviewAction = ReviewAction.RETAIN
    detection_type: DetectionType | None = None
    confidence: float | None = None
    geometry_modified: bool = False

    def __post_init__(self) -> None:
        if not self.region_id or not self.region_id.strip():
            raise ValueError("region_id cannot be empty.")

        if not isinstance(self.provenance, RegionProvenance):
            raise TypeError("provenance must be a RegionProvenance value.")

        if not isinstance(self.action, ReviewAction):
            raise TypeError("action must be a ReviewAction value.")

        if not isinstance(self.geometry_modified, bool):
            raise TypeError("geometry_modified must be a boolean.")

        if self.provenance is RegionProvenance.MANUAL and self.geometry_modified:
            raise ValueError(
                "Manual regions cannot be marked as automatic geometry overrides."
            )

        if self.detection_type is not None and not isinstance(
            self.detection_type, DetectionType
        ):
            raise TypeError("detection_type must be a DetectionType value or None.")

        if self.provenance is RegionProvenance.AUTOMATIC:
            if self.detection_type is None or self.confidence is None:
                raise ValueError(
                    "Automatic regions require a detection type and confidence."
                )

        if self.provenance is RegionProvenance.MANUAL:
            if self.confidence is not None:
                raise ValueError("Manual regions cannot have detector confidence.")

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class ImageReviewPlan:
    """An immutable, revisioned plan bound to one exact source image."""

    plan_id: str
    revision: int
    source_sha256: str = field(repr=False)
    image_width: int
    image_height: int
    settings: ImageSanitizerSettings
    regions: tuple[ReviewRegion, ...] = ()

    def __post_init__(self) -> None:
        if not self.plan_id or not self.plan_id.strip():
            raise ValueError("plan_id cannot be empty.")

        if self.revision < 0:
            raise ValueError("revision cannot be negative.")

        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("Image dimensions must be positive.")

        if (
            len(self.source_sha256) != 64
            or any(character not in string.hexdigits for character in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a 64-character hexadecimal digest.")

        if not isinstance(self.settings, ImageSanitizerSettings):
            raise TypeError("settings must be ImageSanitizerSettings.")

        normalized_regions = tuple(self.regions)
        object.__setattr__(self, "regions", normalized_regions)

        if any(not isinstance(region, ReviewRegion) for region in normalized_regions):
            raise TypeError("regions must contain only ReviewRegion values.")

        region_ids = [region.region_id for region in normalized_regions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("Review region IDs must be unique within a plan.")

        for region in normalized_regions:
            if (
                region.bbox.x2 > self.image_width
                or region.bbox.y2 > self.image_height
            ):
                raise ValueError(
                    f"Review region {region.region_id!r} exceeds image dimensions."
                )

    @property
    def active_regions(self) -> tuple[ReviewRegion, ...]:
        return tuple(
            region for region in self.regions if region.action is ReviewAction.RETAIN
        )

    @property
    def removed_automatic_regions(self) -> tuple[ReviewRegion, ...]:
        return tuple(
            region
            for region in self.regions
            if region.provenance is RegionProvenance.AUTOMATIC
            and region.action is ReviewAction.REMOVE
        )

    @property
    def automatic_removal_count(self) -> int:
        return len(self.removed_automatic_regions)

    @property
    def automatic_geometry_adjustment_count(self) -> int:
        return sum(
            1
            for region in self.regions
            if region.provenance is RegionProvenance.AUTOMATIC
            and region.geometry_modified
        )

    @property
    def manual_addition_count(self) -> int:
        return sum(
            1
            for region in self.active_regions
            if region.provenance is RegionProvenance.MANUAL
        )


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    region_id: str
    action: ReviewAction

    def __post_init__(self) -> None:
        if not self.region_id or not self.region_id.strip():
            raise ValueError("region_id cannot be empty.")

        if not isinstance(self.action, ReviewAction):
            raise TypeError("action must be a ReviewAction value.")


@dataclass(frozen=True, slots=True)
class ReviewGeometryUpdate:
    region_id: str
    bbox: BoundingBox

    def __post_init__(self) -> None:
        if not self.region_id or not self.region_id.strip():
            raise ValueError("region_id cannot be empty.")

        if not isinstance(self.bbox, BoundingBox):
            raise TypeError("bbox must be a BoundingBox.")


@dataclass(frozen=True, slots=True)
class ManualRegionRequest:
    bbox: BoundingBox
    detection_type: DetectionType | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bbox, BoundingBox):
            raise TypeError("bbox must be a BoundingBox.")

        if self.detection_type is not None and not isinstance(
            self.detection_type, DetectionType
        ):
            raise TypeError("detection_type must be a DetectionType value or None.")


@dataclass(frozen=True, slots=True)
class ReviewedImageExportResult:
    output_path: Path = field(repr=False)
    plan_id: str
    plan_revision: int
    applied_plan_regions: tuple[ReviewRegion, ...]
    remediation_detections: tuple[Detection, ...]
    verification: VerificationReport
    redaction_passes: int
    automatic_removal_count: int
    manual_addition_count: int
    automatic_geometry_adjustment_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_path", Path(self.output_path))
        object.__setattr__(
            self,
            "applied_plan_regions",
            tuple(self.applied_plan_regions),
        )
        object.__setattr__(
            self,
            "remediation_detections",
            tuple(self.remediation_detections),
        )

        if self.plan_revision < 0:
            raise ValueError("plan_revision cannot be negative.")

        if self.redaction_passes < 1:
            raise ValueError("redaction_passes must be at least 1.")

        if (
            self.automatic_removal_count < 0
            or self.manual_addition_count < 0
            or self.automatic_geometry_adjustment_count < 0
        ):
            raise ValueError("Review counts cannot be negative.")

    @property
    def detectors_clear(self) -> bool:
        return self.verification.passed

    @property
    def status(self) -> ReviewedOutputStatus:
        if not self.detectors_clear:
            return ReviewedOutputStatus.REVIEW_REQUIRED

        if self.automatic_removal_count or self.automatic_geometry_adjustment_count:
            return ReviewedOutputStatus.VERIFIED_WITH_HUMAN_OVERRIDES

        return ReviewedOutputStatus.PASSED

    @property
    def passed(self) -> bool:
        """True only for an ordinary pass without automatic removals."""

        return self.status is ReviewedOutputStatus.PASSED
