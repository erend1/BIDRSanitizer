from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)
from bidr_sanitizer.vision.signature_yolos import (
    expand_signature_bbox,
    merge_signature_detections,
)


def test_signature_bbox_is_expanded():
    bbox = BoundingBox(
        x1=100,
        y1=100,
        x2=300,
        y2=200,
    )

    expanded = (
        expand_signature_bbox(
            bbox,
            image_width=500,
            image_height=500,
        )
    )

    assert expanded == BoundingBox(
        x1=80,
        y1=80,
        x2=320,
        y2=220,
    )


def test_signature_bbox_is_clamped():
    bbox = BoundingBox(
        x1=5,
        y1=5,
        x2=100,
        y2=50,
    )

    expanded = (
        expand_signature_bbox(
            bbox,
            image_width=120,
            image_height=80,
        )
    )

    assert expanded.x1 == 0
    assert expanded.y1 == 0

    assert expanded.x2 <= 120
    assert expanded.y2 <= 80


def test_duplicate_signatures_are_merged():
    detections = [
        Detection(
            detection_type=(
                DetectionType.SIGNATURE
            ),
            bbox=BoundingBox(
                x1=237,
                y1=269,
                x2=387,
                y2=387,
            ),
            confidence=0.5694,
        ),
        Detection(
            detection_type=(
                DetectionType.SIGNATURE
            ),
            bbox=BoundingBox(
                x1=238,
                y1=256,
                x2=385,
                y2=392,
            ),
            confidence=0.9728,
        ),
    ]

    merged = merge_signature_detections(
        detections
    )

    assert len(merged) == 1

    assert merged[0].bbox == BoundingBox(
        x1=237,
        y1=256,
        x2=387,
        y2=392,
    )

    assert merged[0].confidence == 0.9728


def test_separate_signatures_are_not_merged():
    detections = [
        Detection(
            detection_type=(
                DetectionType.SIGNATURE
            ),
            bbox=BoundingBox(
                50,
                50,
                150,
                100,
            ),
            confidence=0.90,
        ),
        Detection(
            detection_type=(
                DetectionType.SIGNATURE
            ),
            bbox=BoundingBox(
                300,
                200,
                400,
                260,
            ),
            confidence=0.95,
        ),
    ]

    merged = merge_signature_detections(
        detections
    )

    assert len(merged) == 2