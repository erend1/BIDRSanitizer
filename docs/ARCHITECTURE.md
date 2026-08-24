# Architecture

## 1. Overview

BIDR Sanitizer is an offline-first document privacy sanitization
framework.

Its architecture separates four concerns:

1. document-format adaptation;
2. sensitive-information detection;
3. deterministic irreversible redaction;
4. post-redaction verification.

The system currently handles:

- PNG;
- JPEG;
- PDF;
- DOC;
- DOCX;
- TXT.

The central design goal is to reuse the same privacy engines across
different document formats rather than implementing independent
detectors for every format.

## Architecture decisions

Significant privacy and architecture decisions are documented as
Architecture Decision Records in [`docs/adr`](adr/README.md).

Contributors should review the applicable ADRs before changing core
sanitization, model loading, PDF reconstruction, Word conversion, or
verification behavior.

---

## 2. High-Level Architecture

```text
                         INPUT
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
      PNG / JPEG          PDF            DOC / DOCX
          │                │                 │
          │          PDFium rendering      Word COM
          │                │                 │
          │                ▼                 ▼
          │          page images       temporary PDF
          │                │                 │
          └────────────────┴─────────────────┘
                           │
                           ▼
                    IMAGE SANITIZER
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
           OCR          face          signature
             │         detection       detection
             │
             ▼
       text recognizers
             │
             ▼
        Detection[]
             │
             ▼
      deterministic
       pixel redaction
             │
             ▼
        verification
             │
        ┌────┴────┐
        ▼         ▼
      PASSED   REVIEW_REQUIRED
```

TXT uses a separate text-native path:

```text
TXT
 │
 ▼
structured + semantic recognizers
 │
 ▼
TextDetection[]
 │
 ▼
character-span replacement
 │
 ▼
second-pass verification
```

---

## 3. Core Data Model

The privacy pipeline intentionally avoids storing detected sensitive
strings wherever they are unnecessary.

### BoundingBox

A rectangular image region:

```python
BoundingBox(
    x1,
    y1,
    x2,
    y2,
)
```

Coordinates use an upper-left origin.

Bounding boxes support controlled expansion and image-boundary
clamping.

### Detection

Represents image-based sensitive information.

Conceptually:

```python
Detection(
    detection_type,
    bbox,
    confidence,
)
```

### TextSpan

Represents a half-open text interval:

```text
[start, end)
```

### TextDetection

Represents a sensitive text span without requiring storage of the
sensitive text itself.

### DetectionType

Current categories:

```text
TCKN
PHONE
EMAIL
PERSON
ADDRESS
FACE
SIGNATURE
```

---

## 4. Image Sanitization Pipeline

Image sanitization is the primary privacy engine.

Conceptually:

```text
image
  │
  ├── PaddleOCR
  │       │
  │       ▼
  │   OCR text + boxes
  │       │
  │       ├── structured recognizers
  │       │
  │       ├── address context detector
  │       │
  │       └── GLiNER
  │
  ├── YuNet face detector
  │
  └── YOLOS signature detector
          │
          ▼
      detections
          │
          ▼
    bbox expansion
          │
          ▼
    opaque pixel overwrite
          │
          ▼
      output image
          │
          ▼
      verification
```

---

## 5. OCR

OCR is currently provided by PaddleOCR.

Models:

```text
PP-OCRv5_server_det
latin_PP-OCRv5_mobile_rec
```

The OCR adapter produces objects containing:

- recognized text;
- recognition confidence;
- image bounding box.

Sensitive OCR text is excluded from object representations where
possible to reduce accidental logging.

OCR text is combined into a searchable character stream.

Character spans detected by text recognizers are then mapped back to
one or more OCR image boxes.

When a text detection intersects multiple OCR items, their bounding
boxes are unioned.

---

## 6. Structured PII Recognition

Structured recognizers use deterministic patterns and validation.

### TCKN

The TCKN recognizer supports:

- continuous digits;
- spaced digits;
- dotted/separated digits;
- contextual labels.

Checksum-valid TCKNs can be detected without an explicit label.

An 11-digit value with an invalid checksum may still be redacted when
it appears next to explicit identity-number context such as:

```text
T.C. Kimlik No
TC Kimlik
TCKN
Kimlik Numarası
```

This intentionally favors recall.

### Turkish telephone numbers

Multiple forms are supported, including:

```text
0532 123 45 67
05321234567
532 123 45 67
+90 532 123 45 67
0090 532 123 45 67
0212 123 45 67
+90 (212) 123 45 67
```

### E-mail

Conventional e-mail address patterns are detected deterministically.

---

## 7. Semantic PII Recognition

Semantic person-name and address recognition currently uses:

```text
urchade/gliner_multi_pii-v1
```

through a local GLiNER adapter.

Current semantic categories are mapped to:

```text
person  → PERSON
address → ADDRESS
```

The model is loaded from a local directory using offline-loading
behavior.

The sanitizer currently applies semantic recognition both to combined
OCR text and, as a fallback, to appropriate individual OCR lines.

The line-level fallback exists because isolated names may be difficult
to detect when embedded in a larger OCR stream.

---

## 8. Address Context Recognition

Addresses receive an additional deterministic high-recall layer.

Examples of recognized address headers include:

```text
İkamet Adresi
Ev Adresi
Yerleşim Yeri
Tebligat Adresi
Açık Adres
Adres
```

After an explicit address header, nearby OCR lines may be treated as
part of the address block until:

- a stop header is encountered;
- another structural header is found;
- the vertical gap becomes implausibly large;
- the configured following-line limit is reached.

This complements semantic address detection.

---

## 9. Face Detection

Faces are detected using OpenCV YuNet.

A single orientation is insufficient for document evidence because
photographs may appear rotated.

The current detector evaluates:

```text
0°
90°
180°
270°
```

Detections from rotated images are transformed back into the original
image coordinate system.

Face bounding boxes receive safety expansion.

Duplicate detections produced across rotations are merged using IoU and
bbox union.

The use of union is deliberate: duplicate merging must never make the
redaction area smaller.

---

## 10. Signature Detection

Handwritten signatures are detected using:

```text
mdefrance/yolos-small-signature-detection
```

through Transformers/PyTorch.

The current default confidence threshold is intentionally recall
oriented.

Detected signature boxes receive additional horizontal and vertical
expansion.

Overlapping duplicate detections are merged using bbox union and the
maximum confidence.

Again, merged redaction regions must never become smaller than their
inputs.

---

## 11. Redaction

Image redaction is deterministic.

The default visual style is an opaque black rectangle.

Before drawing, bounding boxes are expanded by a configurable safety
margin and clamped to the image dimensions.

The original image object is not modified in place.

Sensitive pixels in the output image are permanently replaced.

Blur and pixelation are intentionally not used because they preserve
information about the original content.

---

## 12. Iterative Sanitization and Verification

The high-level image pipeline performs:

```text
detect
  ↓
redact
  ↓
save
  ↓
re-detect sanitized output
```

If detections remain, additional redaction passes may be performed up
to a configured maximum.

When remediation occurs, redaction is reconstructed from the original
input with the accumulated detections rather than repeatedly modifying
an already compressed image.

This avoids unnecessary repeated compression degradation.

A result contains:

- output path;
- applied detections;
- verification report;
- number of redaction passes.

---

## 13. PDF Pipeline

PDFs are not modified in place.

Each page is rendered to pixels at a configured DPI, normally:

```text
300 DPI
```

The page image is processed by the existing image sanitizer.

Only pages that pass image verification are accepted.

Sanitized pages are then embedded into a completely new PDF.

The final PDF is intentionally image-only.

This removes reliance on the structure of the original PDF and avoids
preserving:

- selectable original text;
- hidden OCR layers;
- original annotations;
- forms;
- document attachments;
- original metadata.

The generated PDF is additionally checked for extractable text.

---

## 14. DOC and DOCX Pipeline

Microsoft Word documents currently use Microsoft Word automation on
Windows.

```text
DOC / DOCX
     │
     ▼
Microsoft Word
     │
     ▼
temporary PDF
     │
     ▼
existing PDF sanitizer
```

The source document is opened read-only.

Macro automation security is forced to disabled while the file is
opened.

The intermediate PDF is not considered safe output.

It exists only as an input adapter to the already-established PDF
pipeline.

Microsoft Word must currently be installed for this adapter.

Word COM automation is intended for local/interactive Windows use and
is not treated as the preferred architecture for unattended server
deployment.

---

## 15. TXT Pipeline

TXT does not require OCR.

The raw text passes through:

```text
structured recognizers
      +
semantic recognizer
```

Detected spans are merged when they overlap.

Sensitive character ranges are replaced from right to left using:

```text
[REDACTED]
```

Right-to-left replacement prevents earlier text offsets from becoming
invalid.

The sanitized string is then scanned again.

---

## 16. Unified Service Layer

`BIDRSanitizerService` is responsible for dispatching files to the
correct adapter.

Conceptually:

```text
.png/.jpg/.jpeg → OfflineImageSanitizer
.pdf            → PDF sanitizer
.doc/.docx      → Word adapter → PDF sanitizer
.txt            → text sanitizer
```

Heavy ML model instances should be initialized once and reused across
multiple files.

This is important for batch processing.

---

## 17. CLI

The command-line layer is intentionally thin.

Its responsibilities include:

- discovering supported files;
- preserving directory structure;
- creating output paths;
- invoking `BIDRSanitizerService`;
- reporting pass/failure state.

Core privacy behavior must not live in CLI code.

The planned UI should follow the same principle.

---

## 18. Model Storage

Model weights are not stored in the repository.

Model setup is exposed through a separate explicit command:

```text
bidr-models install
```

The installer consumes the packaged pinned manifest, downloads only the
declared files into staging, verifies file sizes and SHA-256 hashes, and
promotes verified model directories into the configured external root.
The sanitization service and CLI have no path that invokes this downloader.

`bidr-models check` validates the external installation independently of
model inference.

GLiNER is a special composite installation: its weights come from the
GLiNER repository, while its tokenizer and encoder configuration come from
the pinned mDeBERTa repository. The adapter combines those verified files
in memory during offline initialization; it does not mutate the installed
artifacts or consult a global model cache.

`BIDR_MODELS_DIR` can explicitly define the model root.

The current development environment uses:

```text
C:\BIDRModels
```

with structure:

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

When the environment variable is absent, the configuration layer uses a
platform-appropriate external per-user default.

---

## 19. Planned UI Boundary

A future UI should be built above the service/core layers.

Conceptually:

```text
UI
 │
 ├── file selection
 ├── detector configuration
 ├── threshold controls
 ├── review canvas
 ├── automatic detections
 ├── manual detections
 └── redaction style
        │
        ▼
    core sanitizer
```

UI rendering is not equivalent to privacy redaction.

Any redaction style selected by the UI must eventually produce an opaque,
irreversible replacement in the exported artifact.

---

## 20. Architectural Direction

Future document formats should normally be implemented through adapters.

Preferred:

```text
new format
   ↓
render/convert
   ↓
existing privacy engine
```

Avoid duplicating detector and verifier logic across format-specific
modules.
