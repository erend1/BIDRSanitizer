from __future__ import annotations

from importlib import metadata
import multiprocessing
import os
from pathlib import Path
import sys
import types
from typing import Any
        
from bidr_sanitizer.config import (
    PADDLE_DETECTION_MODEL_DIR,
    PADDLE_RECOGNITION_MODEL_DIR,
    configure_paddle_environment,
)
        
from bidr_sanitizer.models import BoundingBox
from bidr_sanitizer.model_check import (
    require_local_model,
)
from bidr_sanitizer.inference_device import (
    resolve_paddle_device,
)
from bidr_sanitizer.ocr.models import OCRTextItem


_WORKER_START_TIMEOUT_SECONDS = 300.0
_WORKER_RESULT_TIMEOUT_SECONDS = 900.0


def _install_offline_modelscope_stub() -> None:
    """Prevent PaddleX's unused model hub adapter from importing PyTorch."""

    if "modelscope" in sys.modules:
        return

    module = types.ModuleType("modelscope")
    module.__path__ = []

    def unavailable_download(*args, **kwargs):
        raise RuntimeError(
            "ModelScope downloads are disabled; BIDR requires local models."
        )

    module.snapshot_download = unavailable_download
    sys.modules["modelscope"] = module


def _build_paddle_ocr(device: str | None):
    """Initialize Paddle only inside the process that owns its CUDA DLLs."""

    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    configure_paddle_environment()

    import paddle

    if _requires_windows_process_isolation():
        # PaddleX imports ModelScope even when every model path is local and
        # remote source checks are disabled. ModelScope imports PyTorch, whose
        # bundled cuDNN DLLs conflict with Paddle's on Windows. The stub keeps
        # the worker offline and prevents that unused import path.
        _install_offline_modelscope_stub()

    from paddleocr import PaddleOCR

    resolved_device = resolve_paddle_device(paddle, device)
    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_server_det",
        text_detection_model_dir=str(PADDLE_DETECTION_MODEL_DIR),
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        text_recognition_model_dir=str(PADDLE_RECOGNITION_MODEL_DIR),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_rec_score_thresh=0.0,
        device=resolved_device,
        engine="paddle",
    )
    return ocr, resolved_device


def _paddle_gpu_distribution_is_installed() -> bool:
    try:
        metadata.version("paddlepaddle-gpu")
    except metadata.PackageNotFoundError:
        return False
    return True


def _requires_windows_process_isolation() -> bool:
    """Keep Paddle and PyTorch CUDA DLLs out of the same Windows process."""

    return os.name == "nt" and _paddle_gpu_distribution_is_installed()


def _paddle_worker(connection, device: str | None) -> None:
    """Own one Paddle runtime and exchange only in-memory OCR results."""

    try:
        ocr, resolved_device = _build_paddle_ocr(device)
        connection.send(("ready", resolved_device))

        while True:
            try:
                command, payload = connection.recv()
            except EOFError:
                break

            if command == "close":
                break

            if command != "recognize":
                connection.send(("error", "InvalidWorkerCommand"))
                continue

            try:
                results = list(
                    ocr.predict(
                        payload,
                        text_rec_score_thresh=0.0,
                    )
                )
                if len(results) != 1:
                    raise ValueError(
                        "Image OCR did not produce exactly one result."
                    )
                connection.send(("result", results[0].json))
            except Exception as error:
                # Never send OCR text or the input path in diagnostic payloads.
                connection.send(("error", type(error).__name__))
    except Exception as error:
        try:
            connection.send(("startup_error", type(error).__name__))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def parse_paddle_result(
    result_json: dict[str, Any],
) -> list[OCRTextItem]:
    """
    Convert PaddleOCR's public JSON representation into our own
    internal OCR representation.

    Keeping this conversion isolated prevents PaddleOCR-specific
    structures from leaking into the rest of the application.
    """

    payload = result_json.get("res", result_json)

    texts = payload.get("rec_texts", [])
    scores = payload.get("rec_scores", [])
    boxes = payload.get("rec_boxes", [])

    if not (
        len(texts)
        == len(scores)
        == len(boxes)
    ):
        raise ValueError(
            "Unexpected PaddleOCR result: "
            "texts, scores and boxes have different lengths."
        )

    items: list[OCRTextItem] = []

    for text, score, box in zip(
        texts,
        scores,
        boxes,
        strict=True,
    ):
        text = str(text).strip()

        if not text:
            continue

        if len(box) != 4:
            raise ValueError(
                f"Unexpected OCR bounding box shape: {box!r}"
            )

        x1, y1, x2, y2 = (
            int(value)
            for value in box
        )

        items.append(
            OCRTextItem(
                text=text,
                bbox=BoundingBox(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                ),
                confidence=float(score),
            )
        )

    return items


class PaddleOCRAdapter:
    """
    Thin adapter around PaddleOCR.

    The rest of BIDRSanitizer should never depend directly on
    PaddleOCR result objects.
    """

    def __init__(self, *, device: str | None = None) -> None:
        self._ocr = None
        self._worker = None
        self._connection = None
        self._closed = False

        require_local_model(
            "paddle-ocr-detection",
            target_path=(
                PADDLE_DETECTION_MODEL_DIR
            ),
            verify_hashes=False,
        )

        require_local_model(
            "paddle-ocr-recognition",
            target_path=(
                PADDLE_RECOGNITION_MODEL_DIR
            ),
            verify_hashes=False,
        )
        
        if _requires_windows_process_isolation():
            self._start_worker(device)
        else:
            self._ocr, self._device = _build_paddle_ocr(device)

    def _start_worker(self, device: str | None) -> None:
        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe()
        worker = context.Process(
            target=_paddle_worker,
            args=(child_connection, device),
            name="bidr-paddle-ocr",
            daemon=True,
        )
        worker.start()
        child_connection.close()

        self._connection = parent_connection
        self._worker = worker

        if not parent_connection.poll(_WORKER_START_TIMEOUT_SECONDS):
            self.close()
            raise RuntimeError("PaddleOCR worker did not become ready in time.")

        try:
            status, payload = parent_connection.recv()
        except EOFError as error:
            self.close()
            raise RuntimeError("PaddleOCR worker stopped during startup.") from error

        if status != "ready":
            self.close()
            raise RuntimeError(
                f"PaddleOCR worker could not start ({payload})."
            )

        self._device = str(payload)

    @property
    def device(self) -> str:
        return self._device
            

    def recognize(
        self,
        image_path: str | Path,
    ) -> list[OCRTextItem]:
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(image_path)

        if self._closed:
            raise RuntimeError("PaddleOCR adapter is closed.")

        if self._connection is not None:
            self._connection.send(("recognize", str(image_path)))
            if not self._connection.poll(_WORKER_RESULT_TIMEOUT_SECONDS):
                self.close()
                raise RuntimeError("PaddleOCR worker timed out during recognition.")
            try:
                status, payload = self._connection.recv()
            except EOFError as error:
                self.close()
                raise RuntimeError(
                    "PaddleOCR worker stopped during recognition."
                ) from error
            if status != "result":
                raise RuntimeError(
                    f"PaddleOCR worker failed during recognition ({payload})."
                )
            return parse_paddle_result(payload)

        results = list(
            self._ocr.predict(
                str(image_path),
                text_rec_score_thresh=0.0,
            )
        )

        if len(results) != 1:
            raise ValueError(
                "Image OCR was expected to produce exactly "
                f"one result, received {len(results)}."
            )

        result_json = results[0].json

        return parse_paddle_result(result_json)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        connection = self._connection
        worker = self._worker
        self._connection = None
        self._worker = None

        if connection is not None:
            try:
                connection.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass

        if worker is not None:
            worker.join(timeout=10.0)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5.0)

        if connection is not None:
            connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
