# AGENTS.md

This document provides mandatory guidance for AI coding agents and
developers modifying BIDR Sanitizer.

BIDR Sanitizer is a privacy-oriented document sanitization framework.
Changes that appear harmless from a normal application-development
perspective can weaken the privacy guarantees of the system.

Before modifying the project, read:

1. `docs/ARCHITECTURE.md`
2. `docs/PRIVACY_AND_SECURITY.md`
3. `docs/MAINTAINER_HANDOFF.md`
4. `docs/TESTING.md`
5. `docs/MODELS.md`

---

## Core Engineering Invariants

The following rules are architectural requirements.

### 1. Detection and redaction are separate responsibilities

Machine-learning models and deterministic recognizers only determine
which regions or character spans are sensitive.

They must not be responsible for the final destruction of information.

Actual redaction is performed by deterministic code.

For images, sensitive pixels are overwritten.

For text, sensitive character spans are replaced.

---

### 2. Redaction must destroy the underlying information

A visual overlay is not sufficient.

Do not implement privacy redaction using:

- transparency;
- CSS/UI overlays;
- annotations;
- removable PDF objects;
- blur;
- pixelation;
- reversible filters.

The underlying sensitive information must no longer exist in the
sanitized output.

The current image implementation replaces sensitive pixels with opaque
black pixels.

Future visual styles such as white rectangles, flowers, patterns, or
other decorations must still permanently replace the underlying pixels.

---

### 3. High recall is preferred over precision

The application handles privacy-sensitive evidence documents.

Missing a sensitive item is generally more serious than redacting some
additional non-sensitive content.

Do not increase confidence thresholds merely to make outputs visually
cleaner unless the effect on recall has been evaluated.

False positives may later be handled by a human review UI.

False negatives are the primary safety concern.

---

### 4. Never persist detected PII values in logs or audit records

Detection objects should contain information such as:

- detection type;
- bounding box or text span;
- confidence;
- counts.

They should not retain sensitive strings unnecessarily.

Examples of forbidden audit content:

```json
{
  "person": "Ahmet Yılmaz",
  "phone": "0532 123 45 67"
}
```

Preferred form:

```json
{
  "person": 4,
  "phone": 2
}
```

---

### 5. Verification runs on the sanitized output

A successful first detection/redaction pass is not enough.

The sanitized output must be scanned again.

The current pipeline may perform additional redaction passes when
remaining detections are found.

A verifier must not merely assume that previously detected regions were
successfully removed.

---

### 6. Verification is not a legal guarantee

`PASSED` means:

> The currently configured BIDR Sanitizer detectors found no remaining
> detections in the output.

It does not mean:

> The document is guaranteed to contain no sensitive information.

Do not describe detector verification as guaranteed anonymization,
guaranteed KVKK compliance, or an equivalent legal guarantee.

---

### 7. Detector blind spots must be considered

A detector can miss the same object before and after sanitization.

Therefore:

```text
VERIFICATION: PASSED
```

alone does not prove that all sensitive information was found.

Known regression fixtures and manual review are important, especially
when detector models, thresholds, rendering DPI, or coordinate mapping
are changed.

---

### 8. PDF sanitization must not preserve the original PDF internals

The current PDF privacy architecture is:

```text
original PDF
    ↓
render pages to pixels
    ↓
sanitize page images
    ↓
verify page images
    ↓
construct a completely new image-only PDF
```

Do not replace this with in-place PDF rectangle annotations unless a
future design provides equivalent irreversible guarantees.

The final PDF must not copy:

- original text layers;
- hidden OCR text;
- annotations;
- form objects;
- attachments;
- original document structure;
- original metadata.

---

### 9. DOC/DOCX are adapters, not independent privacy engines

DOC and DOCX currently follow:

```text
DOC/DOCX
    ↓
Microsoft Word
    ↓
temporary PDF
    ↓
existing PDF sanitizer
```

Do not implement duplicate PII detection logic specifically for Word
documents unless there is a strong architectural reason.

Document-format adapters should feed the existing sanitization engines.

---

### 10. Models must be local during normal sanitization

Normal document processing must not silently download models.

If a required model is missing, fail clearly.

Do not send document content to hosted AI APIs.

Models are installed separately from the Git repository.

---

### 11. Preserve known stable dependency behavior

The known-good Windows environment currently uses:

- Python 3.13
- PaddleOCR 3.5.0
- PaddlePaddle 3.2.2
- GLiNER 0.2.28

PaddlePaddle 3.3.0 previously caused a Windows CPU/PIR/oneDNN runtime
failure in this project.

Do not casually upgrade foundational ML dependencies simply to remove a
warning.

Read `docs/MAINTAINER_HANDOFF.md` first.

---

### 12. Paddle model paths should be ASCII-safe on Windows

A native Paddle inference issue was encountered when models were stored
under a path containing the Turkish capital `İ`.

The Python layer could see the files while Paddle's native inference
runtime reported existing model files as missing.

Use an ASCII-only external model directory.

The development machine currently uses:

```text
C:\BIDRModels
```

---

## Testing Requirements

Before considering a change complete, run:

```powershell
python scripts\check_public_tree.py
python -m pytest -v
```

Changes affecting actual model integration should additionally run the
appropriate manual/integration tests.

Any change involving:

- bounding boxes;
- coordinate transforms;
- redaction;
- PDF rasterization;
- OCR mapping;
- thresholds;
- model replacement;
- output reconstruction

requires particular attention because these areas directly affect
privacy behavior.

---

## Public Repository Safety

Do not commit:

- real institutional evidence;
- real identity documents;
- real signatures;
- private photographs;
- AI model weights;
- `.venv`;
- generated sanitized outputs;
- temporary Word/PDF files.

Only synthetic or explicitly safe fixtures should appear in the public
repository.

Run:

```powershell
python scripts\check_public_tree.py
```

before staging a release.

---

## Future UI Development

The planned UI may support:

- drag-and-drop files;
- previewing detections;
- manually adding redaction areas;
- removing proposed detections;
- configurable thresholds;
- configurable margins;
- different opaque redaction styles.

The UI must remain a layer above the privacy engine.

Do not move core sanitization logic into UI components.

A future manual removal of an automatically detected region should be
treated as an explicit human override and must be distinguishable from
an automatically verified result.

---

## Preferred Development Principle

When adding a new file format:

```text
new format
   ↓
adapter
   ↓
existing image or text sanitization engine
```

is preferred over:

```text
new format
   ↓
entirely new privacy pipeline
```

Keep privacy-critical logic centralized.