from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw

from bidr_sanitizer.models import BoundingBox


DEFAULT_REDACTION_MARGIN = 5
BLACK = (0, 0, 0)


class RedactionRegion(Protocol):
    """Any geometry-bearing object accepted by deterministic redaction."""

    @property
    def bbox(self) -> BoundingBox:
        ...


ImageOutputTransform = Callable[
    [Image.Image, tuple[RedactionRegion, ...], int],
    Image.Image,
]


def redact_image(
    image: Image.Image,
    detections: Iterable[RedactionRegion],
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
    detections: Iterable[RedactionRegion],
    *,
    margin: int = DEFAULT_REDACTION_MARGIN,
    output_transform: ImageOutputTransform | None = None,
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    regions = tuple(detections)

    with Image.open(input_path) as image:
        redacted = redact_image(
            image,
            regions,
            margin=margin,
        )

        if output_transform is not None:
            redacted = output_transform(
                redacted,
                regions,
                margin,
            )

        save_options = {}
        if output_path.suffix.lower() == ".png" and redacted.mode == "P":
            save_options["optimize"] = True

        redacted.save(output_path, **save_options)

    return output_path
