# Sanitization Pipelines

## Overview

BIDR Sanitizer uses a small number of centralized privacy engines and
adapts supported document formats into those engines.

There are currently two fundamental sanitization domains:

```text
pixel/image domain
text domain
```

PNG, JPEG, PDF, DOC, and DOCX ultimately use the image domain.

TXT uses the text domain.

---

## Image Pipeline

The core image flow is:

```text
INPUT IMAGE
     │
     ▼
OCR + visual detection
     │
     ├── TCKN
     ├── PHONE
     ├── EMAIL
     ├── PERSON
     ├── ADDRESS
     ├── FACE
     └── SIGNATURE
     │
     ▼
Detection[]
     │
     ▼
bbox safety expansion
     │
     ▼
opaque pixel replacement
     │
     ▼
SANITIZED IMAGE
     │
     ▼
run detectors again
     │
     ├── nothing found ─────► PASSED
     │
     └── detection remains
                │
                ▼
         remediation pass
```

The maximum number of remediation passes is configurable.

---

## Text Detection Inside Images

OCR first produces text items containing recognized text, confidence, and
image coordinates.

The OCR text is indexed into a combined character stream.

For example:

```text
OCR item 1: "Telefon:"
OCR item 2: "0532 123 45 67"
OCR item 3: "E-posta:"
OCR item 4: "example@example.com"
```

may conceptually become:

```text
Telefon:
0532 123 45 67
E-posta:
example@example.com
```

with an index mapping each character range back to its OCR item.

Structured and semantic recognizers operate on the text representation.

A detected character span is then mapped back into one or more OCR
bounding boxes.

When one sensitive value spans multiple OCR regions, those regions are
unioned into a single redaction area.

---

## Structured Recognition Path

Structured recognition is deterministic.

```text
OCR text
   │
   ├── TCKN recognizer
   ├── Turkish phone recognizer
   └── e-mail recognizer
          │
          ▼
     TextDetection[]
```

TCKN additionally uses checksum/context logic.

---

## Address Path

Address detection combines:

```text
semantic address recognition
          +
explicit address-context blocks
```

The deterministic block detector is particularly useful for layouts
such as:

```text
İkamet Adresi:
Atatürk Mahallesi
Gül Sokak No: 12
Maltepe / İstanbul
```

where multiple OCR lines collectively represent one address.

---

## Person Path

Person-name detection uses GLiNER.

The recognizer is applied to the combined OCR stream.

A line-level semantic fallback also exists for suitable short OCR lines
because isolated names can otherwise be missed in large combined text.

---

## Face Pipeline

```text
original image
     │
     ├── YuNet at   0°
     ├── YuNet at  90°
     ├── YuNet at 180°
     └── YuNet at 270°
             │
             ▼
map boxes back to original orientation
             │
             ▼
expand safety area
             │
             ▼
merge overlapping duplicates
             │
             ▼
FACE detections
```

Duplicate merging uses bbox union.

Coverage must never shrink during deduplication.

---

## Signature Pipeline

```text
image
  │
  ▼
YOLOS signature detector
  │
  ▼
confidence filtering
  │
  ▼
bbox safety expansion
  │
  ▼
merge overlapping duplicates
  │
  ▼
SIGNATURE detections
```

The default confidence policy favors recall.

---

## Pixel Redaction

All image detections eventually enter one deterministic redactor.

Current form:

```text
Detection[]
     │
     ▼
expand general safety margin
     │
     ▼
clamp to image boundaries
     │
     ▼
overwrite pixels with opaque black
```

The ML detector does not draw the final mask.

This separation allows future visual styles without changing detection.

---

## Remediation Loop

Suppose pass one detects regions A and B.

```text
original
  ↓
redact A+B
  ↓
verify
```

If the verifier finds region C:

```text
original
  ↓
redact A+B+C
  ↓
verify
```

The preferred implementation reconstructs from the original input using
the accumulated detection set.

It does not repeatedly JPEG-compress an already modified intermediate
image.

---

# PNG/JPEG Pipeline

PNG and JPEG are direct image inputs.

```text
PNG/JPEG
   │
   ▼
OfflineImageSanitizer
   │
   ▼
sanitized image
```

The input and output paths must differ.

---

# PDF Pipeline

PDF is treated as a container of pages that must first become pixels.

```text
ORIGINAL PDF
      │
      ▼
open with PDFium
      │
      ▼
initialize form rendering
      │
      ▼
for each page
      │
      ▼
render at configured DPI
      │
      ▼
RGB page image
      │
      ▼
OfflineImageSanitizer
      │
      ▼
verified sanitized page
      │
      └──── repeat for all pages
                     │
                     ▼
        construct brand-new PDF
                     │
                     ▼
      verify no extractable text
                     │
                     ▼
                  OUTPUT
```

Production uses approximately:

```text
300 DPI
```

unless configured otherwise.

Lightweight unit tests may use a lower DPI because they test PDF plumbing
rather than OCR accuracy.

---

## PDF Fail-Closed Behavior

If any page fails privacy verification, the sanitizer should not silently
represent the whole document as successfully sanitized.

The result must either:

```text
fail
```

or:

```text
be explicitly marked REVIEW_REQUIRED
```

depending on the calling workflow.

---

## PDF Reconstruction

The final PDF uses sanitized page images only.

The original PDF object graph is not copied.

This intentionally discards features such as:

```text
original selectable text
hidden OCR text
annotations
forms
attachments
bookmarks
metadata
```

unless a future implementation explicitly reintroduces safe replacements.

---

# DOC/DOCX Pipeline

DOC and DOCX use Microsoft Word only as a renderer.

```text
SOURCE DOC/DOCX
       │
       ▼
Microsoft Word COM
       │
       ├── ReadOnly
       ├── no recent-file addition
       ├── invisible
       └── macro automation disabled
       │
       ▼
temporary PDF
       │
       ▼
normal PDF pipeline
       │
       ▼
image-only sanitized PDF
```

The source document is never modified.

The temporary PDF is not safe output and must not be exposed as if it
were sanitized.

The eventual output extension for Word input is currently PDF.

---

# TXT Pipeline

TXT operates directly on character spans.

```text
TXT
 │
 ▼
decode text
 │
 ├── structured recognizers
 └── semantic recognizer
         │
         ▼
    TextDetection[]
         │
         ▼
merge overlapping spans
         │
         ▼
replace right-to-left
         │
         ▼
     [REDACTED]
         │
         ▼
run detection again
         │
         ├── no detection ─► PASSED
         └── detection ─────► remediation/review
```

Text spans use half-open Python semantics:

```text
[start, end)
```

---

# Unified Dispatch Pipeline

The service layer decides which adapter to invoke.

```text
extension
   │
   ├── .png/.jpg/.jpeg
   │       └── image sanitizer
   │
   ├── .pdf
   │       └── PDF adapter
   │
   ├── .doc/.docx
   │       └── Word adapter
   │              └── PDF adapter
   │
   └── .txt
           └── text sanitizer
```

The calling CLI or future UI should not need to reproduce this logic.

---

# Image Review Pipeline

The implemented PNG/JPEG review workflow is:

```text
file
 │
 ▼
automatic detection
 │
 ▼
Detection Plan
 │
 ▼
interactive review
 │
 ├── add manual box
 ├── retain automatic box
 └── explicitly override/remove box
 │
 ▼
Final Redaction Plan
 │
 ▼
deterministic exporter
 │
 ▼
verification
```

An important distinction is required between:

```text
automatic verification
```

and:

```text
human override of an automatic detection
```

The latter remains visible in the plan and export result. Verifier remediation
does not silently re-add an overlapping detection of the same category.

See `REVIEW_WORKFLOW.md` for source binding, revision conflicts, status
semantics, and atomic output promotion.

---

# Future Redaction Styles

A future style abstraction may support:

```text
solid black
solid white
custom opaque fill
flower/image mask
pattern
```

All styles must satisfy:

```text
original pixels destroyed first
```

A decorative image drawn transparently over recoverable sensitive pixels
is not acceptable.

The style system belongs after the detection/review plan and before final
verification.
