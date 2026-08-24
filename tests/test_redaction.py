from PIL import Image

from bidr_sanitizer.models import (
    BoundingBox,
    Detection,
    DetectionType,
)
from bidr_sanitizer.redaction import redact_image


def test_redaction_replaces_detected_area_with_black_pixels():
    image = Image.new(
        "RGB",
        (200, 200),
        color=(255, 255, 255),
    )

    detection = Detection(
        detection_type=DetectionType.PERSON,
        bbox=BoundingBox(
            x1=50,
            y1=50,
            x2=100,
            y2=100,
        ),
    )

    result = redact_image(
        image,
        [detection],
        margin=0,
    )

    assert result.getpixel((75, 75)) == (0, 0, 0)


def test_pixels_outside_redaction_are_unchanged():
    image = Image.new(
        "RGB",
        (200, 200),
        color=(255, 255, 255),
    )

    detection = Detection(
        detection_type=DetectionType.PHONE,
        bbox=BoundingBox(
            x1=50,
            y1=50,
            x2=100,
            y2=100,
        ),
    )

    result = redact_image(
        image,
        [detection],
        margin=0,
    )

    assert result.getpixel((150, 150)) == (255, 255, 255)


def test_margin_is_also_redacted():
    image = Image.new(
        "RGB",
        (200, 200),
        color=(255, 255, 255),
    )

    detection = Detection(
        detection_type=DetectionType.EMAIL,
        bbox=BoundingBox(
            x1=50,
            y1=50,
            x2=100,
            y2=100,
        ),
    )

    result = redact_image(
        image,
        [detection],
        margin=10,
    )

    # This point is outside the original box but inside
    # the expanded safety margin.
    assert result.getpixel((45, 75)) == (0, 0, 0)


def test_original_image_is_not_modified():
    image = Image.new(
        "RGB",
        (200, 200),
        color=(255, 255, 255),
    )

    detection = Detection(
        detection_type=DetectionType.FACE,
        bbox=BoundingBox(
            x1=50,
            y1=50,
            x2=100,
            y2=100,
        ),
    )

    redact_image(
        image,
        [detection],
        margin=0,
    )

    assert image.getpixel((75, 75)) == (255, 255, 255)