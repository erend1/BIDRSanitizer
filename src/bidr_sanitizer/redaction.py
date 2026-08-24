from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageDraw

from bidr_sanitizer.models import BoundingBox, Detection


DEFAULT_REDACTION_MARGIN = 5
BLACK = (0, 0, 0)


def redact_image(
    image: Image.Image,
    detections: Iterable[Detection],
    *,
    margin: int = DEFAULT_REDACTION_MARGIN,
) -> Image.Image:
    """
    Return a new image in which every detection has been permanently
    overwritten with solid black pixels.

    The original image object is not modified.
    """

    if margin < 0:
        raise ValueError("Margin cannot be negative.")

    output = image.convert("RGB").copy()
    draw = ImageDraw.Draw(output)

    width, height = output.size

    for detection in detections:
        bbox = detection.bbox.expand(
            margin=margin,
            image_width=width,
            image_height=height,
        )

        draw.rectangle(
            [(bbox.x1, bbox.y1), (bbox.x2, bbox.y2)],
            fill=BLACK,
        )

    return output


def redact_image_file(
    input_path: str | Path,
    output_path: str | Path,
    detections: Iterable[Detection],
    *,
    margin: int = DEFAULT_REDACTION_MARGIN,
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        redacted = redact_image(
            image,
            detections,
            margin=margin,
        )

        redacted.save(output_path)

    return output_path