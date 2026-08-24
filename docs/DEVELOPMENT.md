# Development Guide

## Purpose

This document describes how to extend BIDR Sanitizer while preserving its
privacy architecture.

Read these documents before changing core behavior:

```text
AGENTS.md
docs/ARCHITECTURE.md
docs/PRIVACY_AND_SECURITY.md
docs/MAINTAINER_HANDOFF.md
```

---

# Development Principles

The project follows several core principles.

```text
high recall over cosmetic precision
detectors propose regions
deterministic code destroys information
verification operates on sanitized output
models remain local
format adapters reuse central privacy engines
logs avoid sensitive values
```

These are architectural rules, not implementation suggestions.

---

# Repository Layout

The package is organized approximately as:

```text
src/bidr_sanitizer/
│
├── models.py
├── config.py
├── redaction.py
├── text_detection.py
├── text_recognition.py
├── pipeline.py
├── engine.py
├── service.py
├── cli.py
│
├── review/
├── api/
│
├── ocr/
│
├── recognizers/
│   └── semantic/
│
├── vision/
│
├── verification/
│
├── pdf/
│
├── word/
│
└── text/
```

The exact structure may evolve, but privacy responsibilities should remain
separated.

---

# Core Models

`models.py` contains privacy-neutral structural data such as:

```text
DetectionType
BoundingBox
Detection
TextSpan
TextDetection
```

Avoid adding raw sensitive strings to general detection objects.

If raw text must temporarily exist for recognition, keep its lifetime and
exposure limited.

---

# Adding a Structured Recognizer

Structured recognizers belong under:

```text
recognizers/
```

A deterministic recognizer should return:

```text
TextDetection
```

rather than retaining the sensitive value.

Add both positive and negative unit tests.

When appropriate, validate format semantics in addition to regex shape.

Example:

```text
TCKN checksum
```

---

# Adding a Semantic Recognizer

Semantic recognizers should satisfy an abstraction/protocol rather than
being hard-wired throughout the sanitizer.

The current GLiNER adapter is responsible for translating external model
labels into BIDR Sanitizer's internal `DetectionType`.

Do not let third-party label naming leak through the entire codebase.

---

# Adding a Visual Detector

Visual detectors should return:

```text
Detection[]
```

with image-space bounding boxes.

A detector implementation may perform:

```text
model inference
confidence filtering
coordinate transformation
detector-specific bbox expansion
duplicate merging
```

It must not perform final image redaction.

---

# Bounding-Box Safety

When modifying detection boxes:

```text
expansion is generally safe
shrinking requires justification
union is preferred for duplicate privacy detections
clamping must preserve valid image coordinates
```

Never introduce a deduplication method that produces a smaller region than
both source detections without explicit privacy reasoning.

---

# Adding a New Privacy Category

When introducing a new `DetectionType`, update all relevant layers.

Conceptually:

```text
enum/model
   ↓
detector/recognizer
   ↓
sanitization pipeline
   ↓
verification
   ↓
audit counts
   ↓
tests
   ↓
documentation
```

A privacy category should not exist only in the initial detection stage.

---

# Adding a New File Format

Prefer adapting the format to an existing engine.

Examples:

```text
PDF → page images → image sanitizer
DOCX → PDF → image sanitizer
TXT → text sanitizer
```

For a new format, first determine whether it can be converted safely to:

```text
pixels
```

or:

```text
plain text
```

Avoid implementing duplicate TCKN/face/signature logic inside each format
adapter.

---

# Adding a Redaction Style

Future UI versions may support styles other than black.

A safe abstraction might conceptually become:

```python
class RedactionRenderer(Protocol):
    def apply(
        self,
        image,
        detections,
    ):
        ...
```

However, every renderer must satisfy the same privacy property:

```text
original sensitive pixels are destroyed
```

A flower/image/pattern should replace the region, not merely overlay it
with transparency.

---

# Adding Configuration

The review contract currently centralizes its active image export values in
`ImageSanitizerSettings`:

```text
redaction margin
maximum remediation passes
```

Future UI work may require additional configurable values such as:

```text
face threshold
signature threshold
GLiNER thresholds
PDF DPI
redaction style
```

Do not scatter these settings across UI code.

Prefer a typed central configuration object that can be passed into the
service/engine layer.

The default configuration should remain conservative and recall-oriented.

---

# UI Architecture

The UI must depend on the core sanitizer, not vice versa.

Preferred dependency direction:

```text
UI
 ↓
application/service layer
 ↓
core sanitization
 ↓
detectors/adapters
```

Forbidden direction:

```text
core sanitizer
 ↓
UI widget state
```

The core package should remain usable from:

```text
CLI
Python API
future desktop UI
future web UI
tests
```

The current FastAPI adapter lives under `bidr_sanitizer.api`. Core, detector,
redaction, and verification modules must not import it.

API schemas must not expose source paths, source fingerprints, original
filenames, OCR text, or detected PII strings. See `WEB_API.md`.

---

# Review Workflow

The implemented image review contract separates:

```text
automatic detection
human review
final redaction plan
export
verification
```

Do not immediately destroy the only preview copy before the user can
review automatically proposed regions.

Likewise, do not confuse UI preview overlays with exported irreversible
redaction.

---

# Manual Overrides

A user can remove an automatic detection. That action is represented
explicitly in an immutable plan revision.

Conceptually:

```text
automatic detection:
FACE bbox(...)

review:
user_overridden = True
action = remove
```

An output containing an automatic removal is never represented as an
ordinary pass. A clear verifier produces `verified_with_human_overrides`;
a remaining detection produces `review_required`.

See `REVIEW_WORKFLOW.md` for the complete contract.

---

# Model Lifecycle

Heavy models should be initialized once.

A long-lived application/service should reuse:

```text
PaddleOCR
GLiNER
YuNet
YOLOS
```

Do not instantiate the complete engine for every file operation.

---

# Offline Behavior

Normal inference must use local models.

Do not add hosted AI APIs as transparent fallbacks.

If future cloud integrations are ever introduced, they must be explicit,
opt-in, separately documented features.

They must never silently receive user documents.

Model installation is implemented as a separate application boundary.
Only `bidr-models install` may retrieve model artifacts. Core sanitizer,
service, verifier, and detector modules must not import or call the
downloader.

The model inventory is declared in both:

```text
models/manifest.json
src/bidr_sanitizer/resources/model_manifest.json
```

These copies must remain identical. Every model entry requires an
immutable upstream revision, required files, expected sizes, SHA-256
hashes, target directory, provider, and license.

Installer unit tests must use a fake downloader and synthetic tiny files.
Normal unit tests must not retrieve real model assets.

---

# Logging

Do not log OCR text by default.

Do not log sensitive values.

Use metadata such as:

```text
DetectionType.PHONE
page=3
bbox=(...)
confidence=...
```

rather than:

```text
phone=0532...
```

---

# Exceptions

Errors should provide enough information to diagnose configuration
problems without echoing document contents.

Good:

```text
Signature model directory not found:
C:\BIDRModels\signature\...
```

Avoid:

```text
Failed while processing text:
<entire OCR content>
```

---

# Dependency Upgrades

ML dependency upgrades require more care than ordinary package updates.

Particularly sensitive components include:

```text
PaddlePaddle
PaddleOCR
Transformers
GLiNER
PyTorch
Torchvision
OpenCV
pypdfium2
```

Before upgrading:

```text
review changelog
run unit tests
run model integration tests
run mixed regression fixture
inspect output visually
verify offline behavior
```

Do not upgrade solely to silence non-functional warnings.

---

# Model Changes

Changing a model is an architectural change, not merely a dependency bump.

Evaluate:

```text
recall
false positives
coordinate output
confidence distribution
license
offline loading
model size
CPU compatibility
startup time
```

Update:

```text
models/manifest.json
docs/MODELS.md
THIRD_PARTY_NOTICES.md
tests
```

when required.

---

# Code Style

Prefer:

```text
small modules
typed interfaces
protocols around external providers
immutable detection data
explicit failure modes
testable pure functions
```

Privacy-critical transforms should be understandable without reading an
entire ML framework.

---

# Running Development Checks

Before considering work complete:

```powershell
python scripts\check_public_tree.py
python -m pytest -v
```

For changes affecting models, Word conversion, or real document rendering,
run the relevant integration/manual tests as well.

---

# Synthetic Test Data

Public test fixtures must not contain real private information.

Use:

```text
synthetic names
example.com e-mail addresses
clearly synthetic phone values
generated/synthetic TCKN test values
artificial faces
artificial signatures
```

Never commit a colleague's:

```text
photo
signature
identity number
address
private institutional document
```

for convenience.

---

# Documentation Obligation

Changes that alter architectural behavior should update the relevant
documentation in the same pull request.

Typical mappings:

```text
new model         → MODELS + THIRD_PARTY_NOTICES
new pipeline      → ARCHITECTURE + PIPELINES
security behavior → PRIVACY_AND_SECURITY
known issue       → TROUBLESHOOTING
developer rule    → AGENTS / DEVELOPMENT
```

Keeping the documentation synchronized is especially important because
the repository is intended to be understandable by future AI coding
agents as well as humans.
