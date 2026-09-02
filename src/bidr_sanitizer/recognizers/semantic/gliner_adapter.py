from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from bidr_sanitizer.config import (
    GLINER_MODEL_DIR,
)
from bidr_sanitizer.models import (
    DetectionType,
    TextDetection,
    TextSpan,
)
from bidr_sanitizer.model_check import (
    require_local_model,
)
from bidr_sanitizer.inference_device import (
    resolve_torch_device,
)


LABEL_MAPPING = {
    "person": DetectionType.PERSON,
    "address": DetectionType.ADDRESS,
}


_SELF_CONTAINED_FILES = (
    "config.json",
    "spm.model",
    "tokenizer_config.json",
)


def _has_self_contained_backbone(
    model_path: Path,
) -> bool:
    return all(
        (model_path / name).is_file()
        for name in _SELF_CONTAINED_FILES
    )


def _load_self_contained_gliner(
    gliner_class: Any,
    model_path: Path,
    *,
    device: str = "cpu",
) -> Any:
    """
    Load GLiNER without consulting a Hugging Face cache.

    The upstream GLiNER config names its DeBERTa backbone by Hub ID.
    Supplying the verified backbone configuration in memory prevents
    Transformers from resolving that ID while leaving the installed,
    hash-checked upstream files unchanged.
    """
    gliner_config = json.loads(
        (
            model_path
            / "gliner_config.json"
        ).read_text(encoding="utf-8")
    )
    encoder_config = json.loads(
        (
            model_path
            / "config.json"
        ).read_text(encoding="utf-8")
    )

    if not isinstance(gliner_config, dict):
        raise RuntimeError(
            "Local GLiNER configuration must be a JSON object."
        )

    if not isinstance(encoder_config, dict):
        raise RuntimeError(
            "Local GLiNER encoder configuration must be a JSON object."
        )

    local_config = dict(gliner_config)
    local_config["encoder_config"] = encoder_config
    local_config["model_name"] = str(model_path)

    model = gliner_class.from_config(
        local_config,
        backbone_from_pretrained=False,
        map_location="cpu",
    )

    # This mirrors GLiNER 0.2.28's normal checkpoint-loading path,
    # but starts from the fully local configuration above.
    import torch

    state_dict = torch.load(
        model_path / "pytorch_model.bin",
        map_location="cpu",
        weights_only=True,
    )

    model.model.load_state_dict(
        state_dict,
        strict=False,
    )
    del state_dict

    model.model.to(device)
    model.eval()
    return model


class GLiNERPIIRecognizer:
    def __init__(
        self,
        *,
        model_path: str | Path = (
            GLINER_MODEL_DIR
        ),
        person_threshold: float = 0.35,
        address_threshold: float = 0.30,
        device: str | None = None,
    ) -> None:

        if not (
            0.0
            <= person_threshold
            <= 1.0
        ):
            raise ValueError(
                "Person threshold must be "
                "between 0 and 1."
            )

        if not (
            0.0
            <= address_threshold
            <= 1.0
        ):
            raise ValueError(
                "Address threshold must be "
                "between 0 and 1."
            )

        model_path = Path(
            model_path
        ).resolve()

        if model_path == GLINER_MODEL_DIR.resolve():
            require_local_model(
                "gliner-pii",
                target_path=model_path,
                verify_hashes=False,
            )

        elif not model_path.exists():
            raise FileNotFoundError(
                "Local GLiNER model "
                "was not found: "
                f"{model_path}"
            )

        # Absolutely no Hugging Face network access
        # during sanitizer operation.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ[
            "HF_HUB_DISABLE_TELEMETRY"
        ] = "1"

        import torch
        from gliner import GLiNER

        self._device = resolve_torch_device(
            torch,
            device,
        )

        self._person_threshold = (
            person_threshold
        )

        self._address_threshold = (
            address_threshold
        )

        if _has_self_contained_backbone(
            model_path
        ):
            self._model = (
                _load_self_contained_gliner(
                    GLiNER,
                    model_path,
                    device=self._device,
                )
            )

        else:
            self._model = (
                GLiNER.from_pretrained(
                    str(model_path),
                    local_files_only=True,
                )
            )

            model_module = getattr(
                self._model,
                "model",
                None,
            )
            if model_module is not None:
                model_module.to(self._device)

        self._model.eval()

    @property
    def device(self) -> str:
        return self._device

    def recognize(
        self,
        text: str,
    ) -> list[TextDetection]:

        if not text.strip():
            return []

        minimum_threshold = min(
            self._person_threshold,
            self._address_threshold,
        )

        entities: list[dict[str, Any]] = (
            self._model.predict_entities(
                text,
                labels=[
                    "person",
                    "address",
                ],
                threshold=minimum_threshold,
            )
        )

        detections: list[TextDetection] = []

        for entity in entities:
            label = str(
                entity["label"]
            ).lower()

            detection_type = LABEL_MAPPING.get(
                label
            )

            if detection_type is None:
                continue

            score = float(
                entity.get("score", 1.0)
            )

            if (
                detection_type
                == DetectionType.PERSON
                and score < self._person_threshold
            ):
                continue

            if (
                detection_type
                == DetectionType.ADDRESS
                and score < self._address_threshold
            ):
                continue

            start = int(entity["start"])
            end = int(entity["end"])

            if end <= start:
                continue

            detections.append(
                TextDetection(
                    detection_type=detection_type,
                    span=TextSpan(
                        start=start,
                        end=end,
                    ),
                    confidence=score,
                )
            )

        return sorted(
            detections,
            key=lambda detection: (
                detection.span.start,
                detection.span.end,
            ),
        )
