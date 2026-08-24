from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DetectionType(str, Enum):
    TCKN = "tckn"
    PHONE = "phone"
    EMAIL = "email"
    PERSON = "person"
    ADDRESS = "address"
    FACE = "face"
    SIGNATURE = "signature"


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self) -> None:
        if self.x1 < 0 or self.y1 < 0:
            raise ValueError("Bounding box coordinates cannot be negative.")

        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1.")

        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1.")

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def expand(
        self,
        margin: int,
        image_width: int,
        image_height: int,
    ) -> BoundingBox:
        if margin < 0:
            raise ValueError("Margin cannot be negative.")

        if image_width <= 0 or image_height <= 0:
            raise ValueError("Image dimensions must be positive.")

        return BoundingBox(
            x1=max(0, self.x1 - margin),
            y1=max(0, self.y1 - margin),
            x2=min(image_width, self.x2 + margin),
            y2=min(image_height, self.y2 + margin),
        )


@dataclass(frozen=True, slots=True)
class Detection:
    detection_type: DetectionType
    bbox: BoundingBox
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1.")
            

@dataclass(frozen=True, slots=True)
class TextSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("Text span start cannot be negative.")

        if self.end <= self.start:
            raise ValueError("Text span end must be greater than start.")

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class TextDetection:
    detection_type: DetectionType
    span: TextSpan
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1.")