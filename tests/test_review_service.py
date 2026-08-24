from pathlib import Path

import pytest

from bidr_sanitizer.review.models import ImageSanitizerSettings
from bidr_sanitizer.service import BIDRSanitizerService


class FakeImageSanitizer:
    def __init__(self) -> None:
        self.analysis_call = None
        self.export_call = None

    def analyze_for_review(self, input_path, *, settings=None):
        self.analysis_call = (input_path, settings)
        return "synthetic-plan"

    def export_reviewed(self, input_path, output_path, plan):
        self.export_call = (input_path, output_path, plan)
        return "synthetic-result"


def test_service_dispatches_review_analysis_to_long_lived_image_sanitizer():
    fake = FakeImageSanitizer()
    service = BIDRSanitizerService()
    service._image_sanitizer = fake
    settings = ImageSanitizerSettings(redaction_margin=8)

    result = service.analyze_image_for_review("source.png", settings=settings)

    assert result == "synthetic-plan"
    assert fake.analysis_call == (Path("source.png"), settings)


def test_service_dispatches_reviewed_export_to_same_image_sanitizer():
    fake = FakeImageSanitizer()
    service = BIDRSanitizerService()
    service._image_sanitizer = fake

    result = service.export_reviewed_image(
        "source.jpg",
        "safe.png",
        "synthetic-plan",
    )

    assert result == "synthetic-result"
    assert fake.export_call == (
        Path("source.jpg"),
        Path("safe.png"),
        "synthetic-plan",
    )


@pytest.mark.parametrize("path", ["source.pdf", "source", "source.txt"])
def test_service_rejects_non_image_review_without_loading_models(path):
    service = BIDRSanitizerService()

    with pytest.raises(ValueError, match="currently supports PNG and JPEG"):
        service.analyze_image_for_review(path)

    assert service._image_sanitizer is None


def test_service_rejects_non_image_review_output_without_loading_models():
    service = BIDRSanitizerService()

    with pytest.raises(ValueError, match="output must be PNG or JPEG"):
        service.export_reviewed_image("source.png", "safe.pdf", object())

    assert service._image_sanitizer is None
