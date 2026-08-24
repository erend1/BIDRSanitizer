import pytest

from bidr_sanitizer.models import BoundingBox


def test_bbox_dimensions():
    bbox = BoundingBox(
        x1=10,
        y1=20,
        x2=110,
        y2=70,
    )

    assert bbox.width == 100
    assert bbox.height == 50


def test_bbox_expansion():
    bbox = BoundingBox(
        x1=100,
        y1=100,
        x2=200,
        y2=200,
    )

    expanded = bbox.expand(
        margin=10,
        image_width=500,
        image_height=500,
    )

    assert expanded == BoundingBox(
        x1=90,
        y1=90,
        x2=210,
        y2=210,
    )


def test_bbox_expansion_is_clamped_to_image():
    bbox = BoundingBox(
        x1=2,
        y1=3,
        x2=98,
        y2=97,
    )

    expanded = bbox.expand(
        margin=10,
        image_width=100,
        image_height=100,
    )

    assert expanded == BoundingBox(
        x1=0,
        y1=0,
        x2=100,
        y2=100,
    )


def test_invalid_bbox_is_rejected():
    with pytest.raises(ValueError):
        BoundingBox(
            x1=100,
            y1=100,
            x2=50,
            y2=200,
        )


def test_negative_margin_is_rejected():
    bbox = BoundingBox(
        x1=10,
        y1=10,
        x2=20,
        y2=20,
    )

    with pytest.raises(ValueError):
        bbox.expand(
            margin=-1,
            image_width=100,
            image_height=100,
        )