# Testing

## Purpose

Testing in BIDR Sanitizer serves two different goals:

1. software correctness;
2. privacy regression detection.

A test suite that proves only that the program runs is not sufficient for
a privacy-oriented redaction tool.

Changes to detection, coordinate mapping, rendering, thresholds,
redaction, document conversion, or verification can change whether
sensitive information remains visible.

---

## Test Categories

BIDR Sanitizer uses several complementary forms of testing.

```text
unit tests
    │
    ├── deterministic recognizers
    ├── bounding boxes
    ├── OCR mapping
    ├── detection merging
    ├── text sanitization
    ├── PDF reconstruction
    └── verification plumbing

integration tests
    │
    ├── real PaddleOCR
    ├── real GLiNER
    ├── real YuNet
    ├── real YOLOS
    └── Microsoft Word conversion

manual regression tests
    │
    └── known mixed evidence fixtures

human visual review
    │
    └── confirm no sensitive content remains visible
```

No single layer replaces the others.

---

# Running the Unit Test Suite

From the project root:

```powershell
python -m pytest -v
```

For compact output:

```powershell
python -m pytest -q
```

The known-good documentation baseline contains:

```text
166 passing tests
23 passing web-client tests
```

This number will naturally grow as the project evolves.

The important requirement is that no previously passing privacy-related
test is removed or weakened without a documented reason.

---

# Public-Tree Safety Test

Before publishing or committing release candidates, run:

```powershell
python scripts\check_public_tree.py
```

A clean repository should report:

```text
=== BIDR SANITIZER PUBLIC TREE CHECK ===

Summary:
  Sensitive directories: 0
  Forbidden binary/model files: 0
  Other problems: 0

PUBLIC TREE CHECK PASSED
```

This check complements `.gitignore`.

It is intentionally concerned with accidental publication of:

```text
real evidence
private documents
model weights
sensitive directories
forbidden binary artifacts
```

---

# Unit Tests Must Avoid Heavy Runtime Dependencies Where Possible

Ordinary unit tests should not require:

```text
PaddleOCR model loading
GLiNER model loading
YuNet inference
YOLOS inference
Microsoft Word
network access
```

Use protocols, fake providers, synthetic detections, and controlled test
fixtures when testing pipeline behavior.

For example:

```python
class FakeOCRProvider:
    def recognize(self, path):
        return [...]
```

allows OCR mapping and verification logic to be tested without loading
PaddleOCR.

This keeps CI:

```text
fast
deterministic
offline
portable
```

---

# Integration Tests

Integration tests validate behavior that mocks cannot guarantee.

Examples include:

```text
Paddle local model initialization
real OCR inference
GLiNER local inference
rotated-face detection
real signature detection
Word COM conversion
full PDF sanitization
```

These tests may be slower and platform-specific.

They should eventually be marked using pytest markers such as:

```python
@pytest.mark.integration
```

A normal CI run may then use:

```powershell
python -m pytest -m "not integration"
```

while a dedicated integration environment uses:

```powershell
python -m pytest -m integration
```

---

# Model Loading Test

First validate the complete installed model inventory:

```powershell
bidr-models check
```

Model installer unit tests use synthetic byte payloads and a fake
downloader. They cover manifest validation, hash failure, staging,
promotion, idempotency, repair, locking, path safety, and the packaged
GLiNER tokenizer assets without network access.

Release acceptance should additionally test a real installation into an
empty temporary model root. Clear or redirect Hugging Face caches, block
network access after installation, and initialize every adapter. This
ensures GLiNER does not accidentally rely on a pre-existing global
mDeBERTa tokenizer cache.

A useful Paddle smoke test is:

```powershell
python -c "from bidr_sanitizer.ocr.paddle_adapter import PaddleOCRAdapter; PaddleOCRAdapter(); print('External Paddle models OK')"
```

The output should resolve models from the configured external model root.

For the reference Windows development environment:

```text
C:\BIDRModels
```

Expected paths include:

```text
C:\BIDRModels\paddleocr\PP-OCRv5_server_det
C:\BIDRModels\paddleocr\latin_PP-OCRv5_mobile_rec
```

The command should not silently download models.

---

# Structured PII Tests

Deterministic recognizers should include both positive and negative test
cases.

## TCKN

Test:

```text
valid checksum
spaced representation
dotted/separated representation
contextual invalid-checksum value
invalid unlabeled 11-digit value
leading-zero invalid candidate
```

The contextual invalid-checksum behavior is intentional and should not be
removed accidentally.

---

## Phone Numbers

Test multiple Turkish telephone formats and values that must not be
recognized as telephone numbers.

---

## E-mail

Test conventional valid forms as well as malformed values.

---

# Bounding-Box Tests

Bounding-box code is privacy-critical.

Tests should cover:

```text
dimensions
expansion
clamping
invalid coordinates
negative margins
rotation transforms
bbox union
IoU merging
```

A coordinate error may create an apparently successful redaction in the
wrong part of the page.

---

# OCR Mapping Tests

Text detection happens in character space while redaction happens in
image space.

Tests must verify that:

```text
text span
    ↓
correct OCR item(s)
    ↓
correct image bbox
```

Mappings that cross multiple OCR boxes should be explicitly tested.

---

# Face Regression Tests

The face detector must preserve support for:

```text
0°
90°
180°
270°
```

The project previously missed a rotated face when only the original
orientation was scanned.

Do not replace the four-orientation behavior without equivalent regression
coverage.

Duplicate detections from multiple rotations should be merged without
shrinking the redaction region.

---

# Signature Regression Tests

Signature tests should verify:

```text
bbox expansion
boundary clamping
duplicate merging
separate signatures remain separate
```

Real-model integration fixtures should eventually contain varied
signatures such as:

```text
black
blue
small
faint
compressed
partially obscured
```

Threshold changes require integration testing.

---

# Redaction Tests

Image redaction tests should confirm both sides of the operation:

```text
inside bbox  → replaced
outside bbox → unchanged
```

Tests should also verify the safety margin and confirm that the source
image object is not modified unexpectedly.

---

# Verification Tests

Verification tests must cover:

```text
no remaining detections → PASSED
remaining detection     → failure/review
empty OCR               → handled correctly
face verification       → active
signature verification  → active
```

Remember that verifier success does not prove absence of detector blind
spots.

---

# Review Workflow Tests

The interactive image contract should cover:

```text
source hash and dimension binding
immutable plan revisions
stale revision rejection
manual additions
explicit automatic removals
automatic geometry updates
conservative override status
remediation from original pixels
all detectors active on every verification pass
atomic destination preservation on failure
```

Review fixtures must remain synthetic and review objects must not retain OCR
text or other detected PII strings.

---

# Web API Tests

The versioned HTTP adapter should cover:

```text
token, host, origin, and cross-site request rejection
non-cacheable privacy response headers
disabled remote-asset documentation routes
streamed upload byte, decoded-pixel, and PDF page-count limits
PNG/JPEG/PDF media-type and content validation
multi-page PDF analysis and image-only reconstruction
per-page revision conflict behavior
server-side source/path/fingerprint isolation
revision conflict behavior
review export and binary status headers
stale export invalidation
explicit deletion and shutdown cleanup
lazy ML runtime initialization
```

Tests use synthetic in-memory PNG/JPEG/PDF data and fake providers. They must not
start real model inference or open a network connection.

---

# Web Client Tests

From the repository root:

```powershell
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
```

Client tests must cover privacy-relevant presentation and coordinate behavior,
including:

```text
display coordinates → original image pixel coordinates
reverse/out-of-bounds manual drags → normalized/clamped boxes
automatic/manual move and corner resize → bounded source-pixel boxes
authenticated preview requests → no-store and no token in URLs
raw upload → no original filename header or multipart metadata
PDF upload → every page analyzed and navigable through authenticated previews
automatic removal → explicit human override
automatic geometry edit → explicit human override
review_required → never labeled verified safe
plan update → page-specific expected revision, geometry updates, and decisions
```

Tests must use synthetic response data and image bytes. Do not place real
document previews, PII, launch tokens, or exported evidence in client fixtures.

---

# Text Sanitization Tests

Text spans use Python half-open semantics:

```text
[start, end)
```

Tests should prefer:

```python
TextSpan(
    start,
    len(text),
)
```

over manually counting string lengths where appropriate.

Overlapping detections must be merged before replacement.

Replacement occurs from right to left to preserve offsets.

---

# PDF Tests

Unit tests should verify at minimum:

```text
page count preservation
new PDF construction
lack of extractable text
page-size preservation
failure behavior
```

Lightweight unit tests may use a lower render DPI than production.

For example:

```text
unit test: 150 DPI
production: approximately 300 DPI
```

OCR accuracy should be validated separately with integration fixtures.

---

# Word Tests

Ordinary unit tests should not start Microsoft Word.

Instead use a fake implementation of the Word-to-PDF converter protocol.

A separate Windows integration test may validate:

```text
DOCX → Word → PDF
DOC  → Word → PDF
```

on machines where Word is installed.

---

# Known Mixed Regression Fixture

The project should maintain a synthetic mixed-content fixture containing
all supported privacy categories.

Conceptually:

```text
TCKN
PHONE
EMAIL
PERSON
ADDRESS
FACE
SIGNATURE
```

The fixture should also contain rotated faces.

Acceptance should not rely only on:

```text
VERIFICATION: PASSED
```

For a controlled fixture, also confirm that every expected category was
detected.

This guards against a detector becoming completely blind while the same
blind detector still reports a clean verification result.

---

# Visual Review

Before releasing a major detector or rendering change, manually inspect a
representative sanitized output.

Check that:

```text
sensitive content is actually covered
boxes map to correct coordinates
small text remains detectable
rotated faces are covered
signatures are covered
PDF page dimensions remain correct
no original text is selectable in sanitized PDFs
```

Automated tests do not eliminate the need for this step.

---

# Offline Acceptance Test

Before release, perform at least one full real-model sanitization with
network access disabled or blocked.

The workflow should complete using locally installed models.

Unexpected messages about:

```text
fetching
downloading
checking remote model source
```

should be investigated.

Messages such as:

```text
Loading weights: 100%
```

may represent local initialization and are not necessarily network
activity.

---

# Testing New Detectors

A new detector should normally include:

```text
unit tests for adapter logic
bbox/span tests
duplicate-handling tests
verification integration
at least one controlled integration fixture
documentation update
```

Do not add a detector only to the initial detection pass.

If it detects a privacy category, the verifier must understand that
category as well.

---

# Threshold Changes

Detector confidence thresholds are safety-related configuration.

A threshold change should be justified using difficult examples rather
than only clean examples.

For the current project:

```text
false negative risk > cosmetic false positive cost
```

so recall receives priority.

---

# Release Gate

Before preparing a release, run:

```powershell
python scripts\check_public_tree.py
python -m pytest -q
```

Then run the appropriate real-model integration fixture.

Finally inspect staged Git content before publishing:

```powershell
git status
git diff --cached --stat
git diff --cached
```

Never rely solely on `.gitignore` when publishing a privacy-related
repository.
