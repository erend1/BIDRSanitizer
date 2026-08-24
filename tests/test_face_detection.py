from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)
from bidr_sanitizer.vision.yunet import (
    build_expanded_face_bbox,
    merge_face_detections,
    rotate_bbox_back_to_original,
)


def test_face_bbox_is_expanded():
    bbox = build_expanded_face_bbox(
        x=100,
        y=100,
        width=100,
        height=100,
        image_width=500,
        image_height=500,
    )

    assert bbox == BoundingBox(
        x1=75,
        y1=70,
        x2=225,
        y2=230,
    )


def test_face_bbox_is_clamped_to_image():
    bbox = build_expanded_face_bbox(
        x=5,
        y=5,
        width=100,
        height=100,
        image_width=120,
        image_height=120,
    )

    assert bbox.x1 == 0
    assert bbox.y1 == 0
    assert bbox.x2 <= 120
    assert bbox.y2 <= 120


def test_90_degree_bbox_maps_back():
    # Original image: 400 x 300
    #
    # A region in original coordinates:
    # x=100..200, y=50..150
    #
    # After 90° clockwise rotation it maps to:
    # x=150..250, y=100..200

    rotated = BoundingBox(
        x1=150,
        y1=100,
        x2=250,
        y2=200,
    )

    original = (
        rotate_bbox_back_to_original(
            rotated,
            rotation=90,
            original_width=400,
            original_height=300,
        )
    )

    assert original == BoundingBox(
        x1=100,
        y1=50,
        x2=200,
        y2=150,
    )


def test_180_degree_bbox_maps_back():
    rotated = BoundingBox(
        x1=200,
        y1=150,
        x2=300,
        y2=250,
    )

    original = (
        rotate_bbox_back_to_original(
            rotated,
            rotation=180,
            original_width=400,
            original_height=300,
        )
    )

    assert original == BoundingBox(
        x1=100,
        y1=50,
        x2=200,
        y2=150,
    )


def test_270_degree_bbox_maps_back():
    rotated = BoundingBox(
        x1=50,
        y1=200,
        x2=150,
        y2=300,
    )

    original = (
        rotate_bbox_back_to_original(
            rotated,
            rotation=270,
            original_width=400,
            original_height=300,
        )
    )

    assert original == BoundingBox(
        x1=100,
        y1=50,
        x2=200,
        y2=150,
    )


def test_duplicate_face_detections_are_merged():
    detections = [
        Detection(
            detection_type=(
                DetectionType.FACE
            ),
            bbox=BoundingBox(
                100,
                100,
                200,
                200,
            ),
            confidence=0.95,
        ),
        Detection(
            detection_type=(
                DetectionType.FACE
            ),
            bbox=BoundingBox(
                105,
                105,
                205,
                205,
            ),
            confidence=0.88,
        ),
    ]

    merged = merge_face_detections(
        detections
    )

    assert len(merged) == 1

    assert merged[0].bbox == BoundingBox(
        100,
        100,
        205,
        205,
    )

    assert (
        merged[0].confidence
        == 0.95
    )