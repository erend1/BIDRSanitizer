# Maintainer Handoff

## Purpose

This document records implementation knowledge, compatibility findings,
failure modes, architectural decisions, and development lessons discovered
while building the initial BIDR Sanitizer implementation.

It is intended for:

- future maintainers;
- contributors;
- AI coding agents;
- developers debugging deployment problems.

Read `ARCHITECTURE.md` and `PRIVACY_AND_SECURITY.md` first.

---

## Current Project State

The initial sanitization framework currently supports:

```text
PNG
JPEG
PDF
DOC
DOCX
TXT
```

Sensitive categories:

```text
TCKN
PHONE
EMAIL
PERSON
ADDRESS
FACE
SIGNATURE
```

The current unit suite contains 85 passing tests in the known-good
development environment.

The public-tree safety checker also passes.

---

## Known-Good Development Environment

The initial development environment is Windows.

Known-good versions observed during development include:

```text
Python       3.13.x
PaddleOCR    3.5.0
PaddlePaddle 3.2.2
GLiNER       0.2.28
```

Additional runtime components include:

- PyTorch CPU;
- Torchvision CPU;
- Transformers;
- Pillow;
- OpenCV;
- pypdfium2;
- ReportLab;
- pywin32.

Exact release dependency pins should be reviewed in `pyproject.toml`.

---

# PaddlePaddle Compatibility

## PaddlePaddle 3.3.0 problem

A Windows CPU environment using PaddlePaddle 3.3.0 produced a native
PIR/oneDNN failure similar to:

```text
NotImplementedError:
ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]
```

Downgrading to:

```text
paddlepaddle==3.2.2
```

resolved the issue.

Therefore do not upgrade PaddlePaddle casually.

Any future upgrade should run real OCR integration tests rather than
only unit tests.

---

# PaddleOCR Configuration

The project uses PP-OCRv5 rather than PP-OCRv6.

Current local models:

```text
PP-OCRv5_server_det
latin_PP-OCRv5_mobile_rec
```

The Paddle adapter explicitly provides both model names and model
directories.

This is important.

At one point the adapter provided only the local recognition directory.
Paddle attempted to treat it as its default:

```text
PP-OCRv5_server_rec
```

while the directory actually contained:

```text
latin_PP-OCRv5_mobile_rec
```

The adapter now specifies the matching model name explicitly.

Conceptually:

```python
PaddleOCR(
    text_detection_model_name="PP-OCRv5_server_det",
    text_detection_model_dir=...,
    text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
    text_recognition_model_dir=...,
    ...
)
```

---

# Paddle Unicode Path Problem on Windows

This was an important deployment problem.

Models were originally stored inside the project tree.

The project path contained the Turkish character:

```text
RUMELİ
```

Python could confirm that:

```text
inference.json
```

existed.

However Paddle's native C++ inference configuration reported the same
file as missing.

Moving models to an ASCII-only path fixed the problem.

The development environment currently uses:

```text
C:\BIDRModels
```

Recommended rule:

> Use an ASCII-only model root on Windows, especially for Paddle models.

Do not move Paddle model files back underneath the repository merely for
convenience.

---

# Model Root Configuration

Runtime models are intentionally external to the Git repository.

The explicit environment variable is:

```text
BIDR_MODELS_DIR
```

Example:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

The current model layout is:

```text
C:\BIDRModels\
├── paddleocr\
│   ├── PP-OCRv5_server_det\
│   └── latin_PP-OCRv5_mobile_rec\
├── gliner\
│   └── gliner_multi_pii_v1\
├── yunet\
│   └── face_detection_yunet_2023mar.onnx
└── signature\
    └── yolos-small-signature-detection\
```

The repository's `models/` directory should contain metadata and
documentation only.

---

# Offline Model Behavior

The system is designed to avoid runtime model downloads.

GLiNER and Transformers model loading uses local directories and offline
options.

Paddle model paths must also exist locally.

Missing local models should produce an explicit error rather than
falling back to a network download.

An important acceptance test is to run the complete sanitizer without
network access and confirm that no model-fetching messages occur.

A progress display such as:

```text
Loading weights: 100%
```

does not necessarily indicate a download; it may simply be loading
local weights into memory.

---

# Known Transformers Warning

GLiNER currently produces a Transformers warning referring to:

```text
microsoft/mdeberta-v3-base
```

and an alleged incorrect regex pattern with advice related to
`fix_mistral_regex=True`.

This warning did not block GLiNER operation in the known-good
environment.

Do not destabilize the environment by upgrading Transformers solely to
remove this warning.

Investigate separately if it becomes functionally relevant.

---

# OCR Data Handling

`OCRTextItem` contains recognized OCR text but excludes it from
`repr`.

This reduces accidental exposure when objects are logged or printed.

The OCR mapping system builds a combined searchable string and tracks
which character intervals correspond to each OCR item.

Text detections are converted back to image boxes by selecting
intersecting OCR items and unioning their bounding boxes.

---

# Structured PII

## TCKN

TCKN candidates may contain separators.

Checksum validation is used.

A checksum-valid TCKN can be detected without a contextual label.

For high recall, an 11-digit candidate with an invalid checksum may
still be detected when explicit identity-number context is present.

This is intentional.

Real institutional documents can contain mistyped identity numbers, and
privacy redaction should not fail merely because the number contains a
typing error.

---

## Phone numbers

The phone recognizer supports Turkish mobile and landline forms,
including country-code and separator variations.

Unit tests include both positive and negative cases.

---

## E-mail

E-mail recognition is deterministic.

Avoid replacing it unnecessarily with semantic ML.

---

# Address Detection

Addresses use two complementary mechanisms:

1. semantic GLiNER detection;
2. deterministic address-block recognition.

The deterministic mechanism recognizes explicit headers such as:

```text
İkamet Adresi
Ev Adresi
Yerleşim Yeri
Tebligat Adresi
Açık Adres
Adres
```

and may capture several following OCR lines.

Stop headers and vertical spacing are used to prevent the block from
growing indefinitely.

This mechanism exists because multiline addresses are structurally
predictable and should not depend entirely on semantic NER.

---

# Semantic Recognition

The semantic model is:

```text
urchade/gliner_multi_pii-v1
```

Current mapped labels:

```text
person
address
```

The semantic recognizer intentionally stores only spans/types/confidence
in returned detections rather than the sensitive string.

The system uses:

- document-level semantic recognition;
- short line-level fallback recognition.

The fallback was added because isolated person names may be missed when
evaluated only as part of a larger OCR document string.

---

# Face Detection

Face detection uses:

```text
face_detection_yunet_2023mar.onnx
```

A threshold around:

```text
0.45
```

was chosen with recall in mind.

Originally the face detector ran only on the original image
orientation.

A mixed test containing four faces produced only three detections.

The missing face was rotated.

More importantly, post-redaction verification also reported success
because the same detector missed the same face again.

This demonstrated an important principle:

> Verification cannot compensate for detector blind spots.

The YuNet detector was hardened to run four orientations:

```text
0°
90°
180°
270°
```

Detected boxes are transformed back into original coordinates.

Duplicates are merged.

Current face box expansion is deliberately generous.

Do not remove rotation handling.

---

# Signature Detection

The signature detector uses:

```text
mdefrance/yolos-small-signature-detection
```

via Transformers.

Torchvision is required by the image processor.

A missing Torchvision installation previously produced:

```text
ImportError:
AutoImageProcessor requires the Torchvision library
```

The development environment uses CPU PyTorch/Torchvision.

The signature threshold is currently approximately:

```text
0.25
```

This is intentionally low/high-recall.

Do not increase it merely because clean test signatures have high
confidence values.

Real signatures may be:

- faint;
- blue;
- compressed;
- partially obscured;
- stamped over;
- small.

Signature boxes receive additional safety expansion.

Duplicate signature detections are merged with bbox union.

The union is important because privacy-related merging must not shrink
redaction coverage.

---

# Image Redaction

The default image redaction is a solid black rectangle.

The output image is a copy.

Bounding boxes are expanded by a default safety margin before drawing.

Blur and pixelation were deliberately rejected.

Future configurable rendering must preserve irreversible destruction of
underlying pixels.

---

# Iterative Verification

The main image pipeline supports several redaction passes.

Conceptually:

```text
pass 1
detect → redact → verify

remaining?
    ↓
pass 2
accumulate detection → redraw → verify
```

A key implementation detail:

When new detections are discovered during remediation, the output should
be rebuilt from the original input using the accumulated detection set.

Do not repeatedly redraw onto an already recompressed JPEG if it can be
avoided.

This reduces cumulative quality degradation.

The sanitizer also avoids infinite remediation when only detections that
have already been applied recur.

---

# PDF Sanitization

PDF sanitization deliberately prioritizes privacy over preserving
searchability.

Pipeline:

```text
PDF
 ↓
render page at approximately 300 DPI
 ↓
PNG/RGB image
 ↓
existing image sanitizer
 ↓
verified sanitized image
 ↓
new PDF
```

The output PDF is created from sanitized raster images.

It should contain no extractable original text.

This approach also prevents original PDF annotations, hidden text,
attachments, or forms from being copied into the output.

Tests currently verify:

- page count preservation;
- image-only reconstruction.

Production rendering uses higher DPI than lightweight unit tests.

---

# PDF Output Replacement

A Windows `PermissionError` was encountered when attempting to overwrite
a sanitized PDF that was still open in a PDF viewer.

This is normal Windows file-lock behavior.

Future production-quality output writing should favor:

```text
build temporary final PDF
        ↓
verify temporary PDF
        ↓
atomic replace destination
```

rather than directly overwriting an existing valid output.

This prevents a partially written result from replacing a previous
sanitized artifact if PDF creation fails.

---

# Word DOC/DOCX Adapter

LibreOffice is intentionally not required.

On Windows the current adapter uses Microsoft Word through `pywin32`.

Pipeline:

```text
DOC/DOCX
  ↓
Word COM
  ↓
temporary PDF
  ↓
PDF sanitizer
  ↓
image-only sanitized PDF
```

Important Word options include:

```text
ReadOnly=True
AddToRecentFiles=False
Visible=False
DisplayAlerts=False
```

Office automation security is forced to disable macros while the
document is opened.

The source Word document is never modified.

The Word-generated PDF is not considered sanitized.

It exists only as an intermediate renderer output.

This architecture provides far better Word layout fidelity than trying
to reconstruct DOCX pages using a simple XML package such as
`python-docx`.

DOC binary documents are also supported by Word itself.

Do not use Word COM as an unattended web-server architecture without
reconsidering the platform design.

---

# TXT Sanitization

TXT files bypass OCR entirely.

Structured and semantic recognizers produce `TextDetection` instances.

Overlapping spans are merged before replacement.

Sensitive regions are replaced from right to left so that earlier
character offsets remain valid.

The default replacement is:

```text
[REDACTED]
```

The output is then re-scanned.

A unit-test issue once occurred because the test used:

```python
TextSpan(0, 11)
```

for:

```text
Ahmet Yılmaz
```

which contains 12 characters.

The resulting:

```text
[REDACTED]z
```

was correct behavior.

The test was fixed using:

```python
TextSpan(0, len(text))
```

This confirms text spans use end-exclusive semantics.

---

# Service and Model Reuse

Heavy models should be initialized once and reused.

Batch processing must not reload:

```text
PaddleOCR
GLiNER
YuNet
YOLOS
```

for every file.

The service layer exists partly for this reason.

Future UI code should create and retain a long-lived sanitizer service
rather than constructing a new complete engine for each button press.

---

# Public Repository Safety

The repository includes:

```text
scripts/check_public_tree.py
```

Its job is to detect:

- sensitive evidence directories;
- accidentally included model weights;
- other explicitly forbidden artifacts.

Normal development directories such as:

```text
.venv
.pytest_cache
output
__pycache__
```

are skipped because they are already normal ignored local artifacts.

Sensitive directories such as:

```text
private
evidence
kanitlar
real_documents
```

remain explicit failures even if ignored by Git.

This provides defense in depth.

---

# Current Test Baseline

At the documentation checkpoint, the known-good suite contains:

```text
85 passed
```

The public-tree checker reports:

```text
Sensitive directories: 0
Forbidden binary/model files: 0
Other problems: 0

PUBLIC TREE CHECK PASSED
```

External Paddle model loading resolves to:

```text
C:\BIDRModels\paddleocr\PP-OCRv5_server_det
C:\BIDRModels\paddleocr\latin_PP-OCRv5_mobile_rec
```

This is a useful baseline when diagnosing future regressions.

---

# Planned Next Architecture: Review UI

The next major product layer is expected to be an interactive UI.

Likely responsibilities:

```text
drop/select file
      ↓
automatic analysis
      ↓
preview detections
      ↓
manual add/remove/edit
      ↓
threshold/margin configuration
      ↓
redaction-style selection
      ↓
final export
```

The UI should not replace the privacy engine.

It should produce a reviewed/configured detection plan that is then
executed by the existing deterministic redaction pipeline.

Manual removal of automatic detections should eventually be tracked as
an explicit user override.

---

# Development Priority

The next development stages should prioritize:

1. public repository documentation and packaging;
2. stable model installation/check utilities;
3. CI;
4. safe audit reports;
5. configuration objects for thresholds/margins;
6. review-oriented UI.

Do not prematurely refactor the working detector core solely for visual
UI convenience.