from bidr_sanitizer.models import BoundingBox
from bidr_sanitizer.ocr.paddle_adapter import (
    parse_paddle_result,
)


def test_parse_paddle_result():
    result = {
        "res": {
            "rec_texts": [
                "Telefon: 0532 123 45 67",
                "example@rumeli.edu.tr",
            ],
            "rec_scores": [
                0.98,
                0.95,
            ],
            "rec_boxes": [
                [10, 20, 250, 50],
                [10, 70, 280, 100],
            ],
        }
    }

    items = parse_paddle_result(result)

    assert len(items) == 2

    assert items[0].bbox == BoundingBox(
        x1=10,
        y1=20,
        x2=250,
        y2=50,
    )

    assert items[0].confidence == 0.98


def test_empty_ocr_text_is_ignored():
    result = {
        "res": {
            "rec_texts": [
                "",
                "0532 123 45 67",
            ],
            "rec_scores": [
                0.2,
                0.99,
            ],
            "rec_boxes": [
                [10, 10, 20, 20],
                [30, 30, 200, 60],
            ],
        }
    }

    items = parse_paddle_result(result)

    assert len(items) == 1


def test_ocr_text_is_hidden_from_repr():
    result = {
        "res": {
            "rec_texts": [
                "0532 123 45 67",
            ],
            "rec_scores": [
                0.99,
            ],
            "rec_boxes": [
                [10, 10, 200, 50],
            ],
        }
    }

    item = parse_paddle_result(result)[0]

    representation = repr(item)

    assert "0532" not in representation
    assert "123" not in representation