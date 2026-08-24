# Usage

## Overview

BIDR Sanitizer can be used through:

```text
Python API
command-line interface
```

A graphical review UI is planned for a future release.

The command-line interface automatically dispatches supported file types
to the appropriate sanitization pipeline.

## Model setup

Model retrieval is an explicit operation separate from document
sanitization:

```powershell
bidr-models install
bidr-models check
```

`bidr-models install` may access the network to retrieve pinned public
model artifacts. `bidr-sanitize` never invokes it automatically.

For an ASCII-safe custom Windows model root:

```powershell
bidr-models install --models-dir C:\BIDRModels
$env:BIDR_MODELS_DIR = "C:\BIDRModels"
bidr-models check
```

---

## Supported Inputs

| Extension | Processing path | Output |
| --- | --- | --- |
| `.png` | Image sanitizer | PNG |
| `.jpg` | Image sanitizer | JPEG |
| `.jpeg` | Image sanitizer | JPEG |
| `.pdf` | Rasterized PDF pipeline | Image-only PDF |
| `.doc` | Microsoft Word → PDF pipeline | Image-only PDF |
| `.docx` | Microsoft Word → PDF pipeline | Image-only PDF |
| `.txt` | Text-span sanitizer | TXT |

DOC/DOCX currently requires Microsoft Word on Windows.

---

# Command-Line Usage

After installation:

```powershell
bidr-sanitize --help
```

Alternatively:

```powershell
python -m bidr_sanitizer --help
```

---

## Sanitize One Image

```powershell
bidr-sanitize ".\evidence.png"
```

Default output is written under the configured/default output directory.

A typical output name is:

```text
evidence_REDACTED.png
```

---

## Sanitize One PDF

```powershell
bidr-sanitize ".\evidence.pdf"
```

The output is a newly constructed image-only PDF:

```text
evidence_REDACTED.pdf
```

The original PDF is not modified.

---

## Sanitize DOCX

```powershell
bidr-sanitize ".\evidence.docx"
```

DOCX currently becomes a sanitized PDF.

A collision-safe output name may use:

```text
evidence_DOCX_REDACTED.pdf
```

The Word document itself is not modified.

---

## Sanitize Legacy DOC

```powershell
bidr-sanitize ".\evidence.doc"
```

Legacy DOC is also rendered through locally installed Microsoft Word.

A collision-safe output may use:

```text
evidence_DOC_REDACTED.pdf
```

---

## Sanitize TXT

```powershell
bidr-sanitize ".\evidence.txt"
```

Detected sensitive character spans are replaced with:

```text
[REDACTED]
```

---

## Choose an Output Directory

```powershell
bidr-sanitize ".\evidence.pdf" -o ".\safe_output"
```

---

## Process a Directory

```powershell
bidr-sanitize ".\evidence_folder" -o ".\safe_output"
```

Supported files in the directory are processed.

---

## Recursive Batch Processing

```powershell
bidr-sanitize ".\evidence_folder" `
    --recursive `
    -o ".\safe_output"
```

The relative directory structure should be preserved.

For example:

```text
evidence_folder/
├── A.1.1/
│   └── meeting.pdf
└── B.2.1/
    └── participants.docx
```

becomes approximately:

```text
safe_output/
├── A.1.1/
│   └── meeting_REDACTED.pdf
└── B.2.1/
    └── participants_DOCX_REDACTED.pdf
```

---

# Result Meaning

A successful operation may report:

```text
PASSED
```

This means the configured verification pipeline found no remaining
detections in the sanitized output.

It does not guarantee that every possible sensitive item was identified.

Human review remains recommended for important evidence documents.

See:

```text
docs/PRIVACY_AND_SECURITY.md
```

---

# Python API

## High-Level Image Sanitizer

```python
from bidr_sanitizer.engine import OfflineImageSanitizer


sanitizer = OfflineImageSanitizer()

result = sanitizer.sanitize(
    "input.png",
    "output_REDACTED.png",
)

print(result.passed)
print(result.redaction_passes)
```

The sanitizer initializes the required local models and reuses them for
subsequent calls.

For multiple files, reuse the same sanitizer instance.

---

## PDF

```python
from bidr_sanitizer.engine import OfflineImageSanitizer
from bidr_sanitizer.pdf.sanitizer import sanitize_pdf


image_sanitizer = OfflineImageSanitizer()

result = sanitize_pdf(
    "input.pdf",
    "output_REDACTED.pdf",
    sanitizer=image_sanitizer,
    dpi=300,
)

print(result.passed)
print(result.page_count)
print(result.text_layer_empty)
```

---

## DOC/DOCX

```python
from bidr_sanitizer.engine import OfflineImageSanitizer
from bidr_sanitizer.word.sanitizer import sanitize_word_document
from bidr_sanitizer.word.word_com import WordCOMConverter


image_sanitizer = OfflineImageSanitizer()
word_converter = WordCOMConverter()

result = sanitize_word_document(
    "input.docx",
    "output_REDACTED.pdf",
    converter=word_converter,
    sanitizer=image_sanitizer,
    dpi=300,
)

print(result.passed)
print(result.page_count)
```

---

## TXT

```python
from bidr_sanitizer.engine import OfflineImageSanitizer
from bidr_sanitizer.text.sanitizer import sanitize_text_file


image_sanitizer = OfflineImageSanitizer()

result = sanitize_text_file(
    "input.txt",
    "output_REDACTED.txt",
    semantic_recognizer=(
        image_sanitizer.semantic_recognizer
    ),
)

print(result.passed)
```

Reusing the semantic recognizer avoids loading GLiNER twice.

---

# Unified Service

For applications that accept multiple formats, prefer the service layer.

```python
from bidr_sanitizer.service import BIDRSanitizerService


service = BIDRSanitizerService()

input_path = "document.pdf"
output_path = "document_REDACTED.pdf"

result = service.sanitize_file(
    input_path,
    output_path,
)

print(result.passed)
```

A long-lived UI should normally create one service instance and reuse it.

Do not instantiate the full model stack for every button press.

---

# Current Detection Categories

The core detection enumeration currently includes:

```text
TCKN
PHONE
EMAIL
PERSON
ADDRESS
FACE
SIGNATURE
```

Different formats may produce multiple detections for the same physical
region.

This is expected.

For example, text may simultaneously participate in semantic and
deterministic recognition.

Logical detection counts therefore do not always equal the number of
physical rectangles visible in the final document.

---

# Redaction Appearance

The current image redaction style is an opaque black rectangle.

TXT uses:

```text
[REDACTED]
```

Alternative opaque image redaction styles are planned.

The implementation requirement is that the original information must be
destroyed rather than merely covered by a removable visual layer.

---

# Model Configuration

Set the external model root before starting the application when using a
custom location:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

See:

```text
docs/MODELS.md
```

---

# PDF Size

Sanitized PDFs may be significantly larger than their source documents.

This is expected because pages are rasterized at high resolution and
embedded into a new PDF.

The initial implementation intentionally prioritizes privacy and OCR
quality over aggressive output compression.

Future releases may provide configurable safe compression.

---

# PDF Searchability

The sanitized PDF is intentionally image-only.

Therefore:

```text
Ctrl+A / Ctrl+C
```

will normally not copy the original PDF text.

This is a deliberate privacy property, not a bug.

---

# Word Files

DOC and DOCX currently require Microsoft Word.

LibreOffice is not required.

The Word-generated intermediate PDF is temporary and must not be treated
as sanitized output.

The final result passes through the same rasterized PDF privacy pipeline
as native PDFs.

---

# Review Required

When the sanitizer cannot verify an output successfully, the caller
should treat the artifact as:

```text
REVIEW_REQUIRED
```

Do not distribute a document solely because an output file was created.

The verification state is the relevant result.

---

# Batch Performance

Model initialization is expensive.

Batch operations should therefore use one long-lived service:

```text
load Paddle
load GLiNER
load YuNet
load YOLOS
       ↓
process all files
```

rather than reloading models for each document.

---

# Review Application Foundation

The current Python application layer supports source-bound PNG/JPEG analysis,
immutable review revisions, manual boxes, explicit automatic-region removals,
deterministic reviewed export, and output verification.

See:

`docs/REVIEW_WORKFLOW.md`

The same workflow is available through the authenticated `/api/v1` adapter.
See:

`docs/WEB_API.md`

The graphical interface is expected to provide:

```text
file drag-and-drop
automatic redaction preview
manual box addition
manual detection override
threshold configuration
margin configuration
alternative opaque redaction styles
final verification
```

The UI will use this review/service contract rather than
implementing an independent sanitizer.
