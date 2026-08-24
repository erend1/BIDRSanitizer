# Local Models

BIDR Sanitizer performs document analysis locally.

Runtime sanitization does not silently download model files. Required
models must be installed before the corresponding detection capability
is used.

## Default model directory

On Windows, BIDR Sanitizer uses:

    %LOCALAPPDATA%\BIDRSanitizer\models

A typical installation therefore looks like:

    C:\Users\<user>\AppData\Local\BIDRSanitizer\models

Most users should use this default and do not need to configure an
environment variable.

The expected structure is:

    models/
    ├── paddleocr/
    │   ├── PP-OCRv5_server_det/
    │   └── latin_PP-OCRv5_mobile_rec/
    ├── gliner/
    │   └── gliner_multi_pii_v1/
    ├── yunet/
    │   └── face_detection_yunet_2023mar.onnx
    └── signature/
        └── yolos-small-signature-detection/

## Custom model directory

Advanced users may override the default directory with
`BIDR_MODELS_DIR`.

PowerShell example:

    $env:BIDR_MODELS_DIR = "D:\BIDRModels"

An explicit `BIDR_MODELS_DIR` always takes precedence over the default
location.

On Windows, an ASCII-only model path is recommended because some native
inference backends may not reliably handle non-ASCII model paths.

## PaddleX cache

Unless `PADDLE_PDX_CACHE_HOME` is explicitly configured, BIDR Sanitizer
uses:

    %LOCALAPPDATA%\BIDRSanitizer\paddlex_cache

This directory is separate from the required model files.

## Offline behavior

Model installation and runtime inference are separate operations.

BIDR Sanitizer does not treat a missing model as permission to
automatically retrieve it during sanitization. If a required local model
is absent, processing fails explicitly.

## Overview

BIDR Sanitizer uses multiple specialized local models rather than one
general-purpose hosted AI service.

The current model stack is:

| Component | Model | Purpose |
| --- | --- | --- |
| OCR detection | `PP-OCRv5_server_det` | Locate text regions |
| OCR recognition | `latin_PP-OCRv5_mobile_rec` | Recognize text |
| Semantic PII | `urchade/gliner_multi_pii-v1` | Person/address recognition |
| Face detection | `face_detection_yunet_2023mar.onnx` | Detect faces |
| Signature detection | `mdefrance/yolos-small-signature-detection` | Detect handwritten signatures |

Structured TCKN, phone, e-mail, and address-context recognition does not
require a machine-learning model.

---

## Model Storage Philosophy

Model weights are not committed to the BIDR Sanitizer Git repository.

This is intentional.

Models are external runtime dependencies because they may be large,
have independent release cycles, and remain subject to their own licenses.

The repository stores only:

```text
models/
├── README.md
└── manifest.json
```

The actual weights live in an external directory.

---

## Recommended Windows Model Root

The current known-good location is:

```text
C:\BIDRModels
```

Recommended structure:

```text
C:\BIDRModels\
├── paddleocr\
│   ├── PP-OCRv5_server_det\
│   └── latin_PP-OCRv5_mobile_rec\
│
├── gliner\
│   └── gliner_multi_pii_v1\
│
├── yunet\
│   └── face_detection_yunet_2023mar.onnx
│
└── signature\
    └── yolos-small-signature-detection\
```

---

## Model Root Configuration

The highest-priority configuration mechanism is:

```text
BIDR_MODELS_DIR
```

Example:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

BIDR Sanitizer then derives every individual model path from that root.

This keeps model configuration centralized.

---

## PaddleOCR

BIDR Sanitizer currently uses:

```text
PP-OCRv5_server_det
latin_PP-OCRv5_mobile_rec
```

The Paddle adapter explicitly provides both model names and local model
directories.

The recognition model name must match the recognition model directory.

Do not remove the explicit model-name configuration.

An earlier configuration allowed Paddle to assume:

```text
PP-OCRv5_server_rec
```

while the local directory contained:

```text
latin_PP-OCRv5_mobile_rec
```

which caused model initialization problems.

---

## Paddle Model Directory Requirements

Both local Paddle directories must contain the complete model artifacts
required by Paddle's inference runtime.

BIDR Sanitizer treats missing model directories as installation errors.

Normal runtime must not silently download a replacement.

---

## Paddle Windows Path Limitation

An important native-library compatibility problem was discovered during
development.

A model directory underneath a path containing:

```text
RUMELİ
```

was visible to Python but not correctly resolved by Paddle's native C++
inference layer.

For that reason, use an ASCII-only model root on Windows.

Recommended:

```text
C:\BIDRModels
```

Avoid placing Paddle runtime models inside arbitrary user/repository paths
containing non-ASCII characters.

---

## Semantic PII Model

The semantic recognizer currently uses:

```text
urchade/gliner_multi_pii-v1
```

It is used for semantic labels that are mapped to BIDR Sanitizer
detection types.

Current mapping:

```text
person  -> PERSON
address -> ADDRESS
```

GLiNER is not responsible for final redaction.

It returns character spans and confidence information, which are mapped
into the appropriate text/image regions.

---

## GLiNER Offline Loading

The GLiNER adapter loads from a local path.

Offline Hugging Face behavior is enabled during normal runtime.

If the model directory is absent, initialization should fail rather than
fetching a model automatically.

---

## Known Tokenizer Warning

The current stack may display a Transformers warning mentioning:

```text
microsoft/mdeberta-v3-base
```

and an incorrect regex pattern.

The warning has not prevented correct operation in the known-good
development environment.

Do not upgrade Transformers or modify tokenizer behavior solely to
silence the warning without regression testing the semantic detector.

---

## YuNet Face Detector

Face detection uses:

```text
face_detection_yunet_2023mar.onnx
```

The current implementation runs detection at:

```text
0°
90°
180°
270°
```

This is a privacy-critical behavior.

An earlier implementation evaluated only the original orientation and
missed a rotated face. The post-redaction verifier then also missed the
same face.

That incident demonstrated that repeated use of the same detector does
not eliminate detector blind spots.

Do not remove multi-orientation face detection without an equivalent
replacement.

---

## Signature Model

Signature detection currently uses:

```text
mdefrance/yolos-small-signature-detection
```

through Transformers and PyTorch.

Torchvision is required by the image processor.

The default signature threshold is intentionally recall-oriented.

A clean sample may produce very high confidence scores, but real
institutional signatures can be:

```text
faint
blue
small
compressed
partially stamped
partially occluded
```

Do not increase the threshold solely based on clean test fixtures.

---

## Model Threshold Philosophy

BIDR Sanitizer generally prefers recall over precision.

The privacy cost of:

```text
missed sensitive region
```

is usually greater than the usability cost of:

```text
extra black rectangle
```

Future UI versions may expose configurable detector thresholds, but the
safe/default configuration should remain recall-oriented.

Custom threshold changes should be recorded as user configuration.

---

## Model Initialization and Reuse

PaddleOCR, GLiNER, YuNet, and YOLOS should be initialized once per
long-lived sanitizer service.

Do not reload heavy models for every file in batch processing or every
UI interaction.

Preferred lifecycle:

```text
application starts
      ↓
initialize models
      ↓
process file A
      ↓
process file B
      ↓
process file C
      ↓
application exits
```

---

## Model Verification

After installing models, verify at least the Paddle stack:

```powershell
python -c "from bidr_sanitizer.ocr.paddle_adapter import PaddleOCRAdapter; PaddleOCRAdapter(); print('External Paddle models OK')"
```

Run the complete manual/integration sanitizer fixture before releasing a
new model configuration.

A full acceptance test should include all current sensitive categories:

```text
TCKN
PHONE
EMAIL
PERSON
ADDRESS
FACE
SIGNATURE
```

It should also include rotated faces and varied signatures.

---

## Model Manifest

The repository contains:

```text
models/manifest.json
```

This file is intended to become the machine-readable source of truth for
model setup and diagnostics.

Future versions should extend the manifest with:

```text
upstream revision
required filenames
download source
checksums
license metadata
```

Model-download/setup utilities should consume the manifest rather than
hard-code model information independently.

---

## Future Model Setup Utility

A future supported installation workflow is expected to provide commands
such as:

```powershell
python scripts\setup_models.py --models-dir C:\BIDRModels
```

and:

```powershell
python scripts\check_models.py
```

Until those utilities are finalized, model installation is an explicit
deployment step.

The sanitizer itself must not compensate for missing installation by
silently downloading models during document processing.

---

## Third-Party Licensing

Models and runtime libraries remain subject to their own licenses.

See:

```text
THIRD_PARTY_NOTICES.md
```

before redistributing model files.

The BIDR Sanitizer source-code license does not automatically relicense
third-party model artifacts.