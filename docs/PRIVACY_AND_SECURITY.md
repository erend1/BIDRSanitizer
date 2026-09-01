# Privacy and Security Model

## Purpose

BIDR Sanitizer is designed to reduce the risk of exposing sensitive
information when documents are shared as institutional evidence or for
similar document-processing workflows.

The system combines deterministic recognizers, local machine-learning
models, irreversible redaction, and post-redaction verification.

It is a technical privacy tool, not a legal compliance certification
system.

---

## Privacy Goals

The project aims to provide the following properties:

### Local processing

After required models are installed locally, ordinary document
sanitization is designed to run without sending document contents to
hosted AI services.

### Irreversible exported redaction

Sensitive content should be destroyed in the exported artifact rather
than merely visually hidden.

### Minimal sensitive logging

Sensitive values should not be persisted in application logs or audit
reports.

### High recall

The system prefers additional redaction over silently leaving sensitive
content visible.

### Verification

Sanitized output is scanned again rather than trusting the initial
detection pass.

---

## Current Sensitive Categories

The current system detects:

- Turkish Republic identification numbers;
- Turkish telephone numbers;
- e-mail addresses;
- person names;
- addresses;
- human faces;
- handwritten signatures.

This list is not exhaustive with respect to every possible category of
personal or confidential information.

---

## Threat Model

The project primarily addresses accidental disclosure of sensitive
information through ordinary document sharing.

Examples include:

- a TCKN appearing in a meeting document;
- a telephone number in a participant list;
- an e-mail address in a screenshot;
- a home address in a form;
- a face in an embedded photograph;
- a handwritten signature;
- selectable sensitive text hidden behind an apparent PDF rectangle.

The system attempts to eliminate both visible sensitive content and
certain hidden document structures by reconstructing outputs.

---

## What the System Does Not Guarantee

BIDR Sanitizer cannot guarantee detection of every sensitive item.

Machine-learning systems and OCR can fail.

Examples include:

- unreadable scans;
- unusual handwriting;
- severe image compression;
- unsupported languages;
- unusual identity-number formats;
- obscured faces;
- unusual signatures;
- handwritten addresses;
- semantic PII outside the currently configured categories.

A `PASSED` result therefore means only:

> The currently enabled verification detectors found no remaining
> detections in the sanitized output.

It does not mean:

> The document is guaranteed free of sensitive information.

Human review remains recommended for important or high-risk evidence.

---

## Detector Blind Spots

Verification reuses the same detector families used during sanitization.

This creates an important limitation:

```text
detector misses item before redaction
          +
detector misses same item after redaction
          =
verification may still report PASSED
```

For that reason, regression fixtures and human inspection remain
important.

The project previously encountered this problem with a rotated face.
The face detector was subsequently extended to evaluate 0, 90, 180 and
270 degree orientations.

This incident is representative of why verification must not be
interpreted as proof of completeness.

---

## Redaction Safety

### Image outputs

Detected regions are permanently overwritten with opaque pixels.

The current default is black.

Blur and pixelation are not considered privacy-safe redaction methods
because they preserve information derived from the original pixels.

### TXT outputs

Sensitive character ranges are replaced with:

```text
[REDACTED]
```

The original characters are not written to the output.

### PDF outputs

The original PDF is not modified in place.

Instead:

```text
original PDF
   ↓
page rasterization
   ↓
image sanitization
   ↓
new image-only PDF
```

The original PDF's structural objects are not reused.

This is intended to prevent sensitive information from surviving in:

- text layers;
- annotations;
- form fields;
- hidden OCR text;
- document attachments;
- metadata.

---

## Temporary Files

PDF and Word adapters may create temporary intermediate files.

Reviewed image export also creates a temporary candidate beside the requested
destination. Verification runs on that candidate and the destination is
replaced atomically only after processing completes. A failed verifier call
does not replace an existing destination with a partial artifact.

Temporary files are removed during normal cleanup.

Deletion of temporary files must not be described as guaranteed secure
erasure, particularly on SSDs or modern filesystems.

Users handling highly sensitive data should apply appropriate operating
system and storage security controls.

---

## DOC/DOCX Considerations

DOC and DOCX conversion currently uses locally installed Microsoft Word
on Windows.

The document is opened read-only.

Macro execution is disabled for automation.

The resulting Word-generated PDF is only an intermediate representation
and is never considered the final sanitized artifact.

The project's local-processing statement concerns BIDR Sanitizer itself.
Behavior of Microsoft Office installations may also depend on the
user's Office configuration and organizational policies.

---

## Model Downloads

Models should be installed before document processing.

The separate, explicit command:

```text
bidr-models install
```

may contact the declared public model repositories. It sends model
identifiers and pinned revisions, never user documents, OCR text, images,
or detected values.

Normal sanitizer runtime must not silently download missing models.

If a required model is unavailable, the preferred behavior is to stop
with an explicit installation error.

This avoids unexpectedly transmitting model-related requests from
restricted/offline environments and makes deployment behavior
predictable.

---

## Logs and Audit Data

Application logs must avoid sensitive contents.

Safe information includes:

```text
detection type
bounding box
confidence
page number
count
verification state
redaction pass count
```

Avoid storing:

```text
OCR text
detected names
identity numbers
telephone numbers
e-mail addresses
addresses
```

unless a future feature has an explicit, documented, privacy-reviewed
reason for doing so.

---

## Manual Review UI

The image review application contract allows users to:

- add redaction boxes;
- remove proposed redaction boxes;
- move and resize proposed or manual redaction boxes;
- modify safety margins.

Threshold controls and alternative opaque styles remain future work.

These capabilities introduce new safety requirements.

### Manual addition

A manually added redaction region should be treated as equivalent to an
additional sensitive detection region.

### Manual removal

Removing an automatically proposed redaction creates an explicit human
override.

The application does not silently present such an artifact as equivalent to
a fully automatic `PASSED` result. It distinguishes
`verified_with_human_overrides` from `passed`, and remediation cannot silently
re-add the explicitly removed region.

Moving or resizing an automatically proposed box is also an explicit human
override. The adjusted geometry is source-bound, included in the immutable
plan revision, and reported in the export receipt. Verification still runs on
the generated output.

### Redaction styles

Alternative styles such as:

- white rectangles;
- decorative flowers;
- patterns;
- other opaque graphics

are acceptable only if the underlying sensitive pixels are first
permanently destroyed.

A decorative overlay alone is not sufficient.

---

## Local Web API Boundary

The `/api/v1` review adapter keeps uploaded sources, source fingerprints, and
export files in private server-side session workspaces. JSON responses expose
geometry and review metadata, not OCR text, detected strings, source paths, or
original filenames.

All document/session endpoints require a strong per-launch token. The adapter
also enforces configured host and origin values, rejects cross-site browser
requests, enables no CORS policy, disables remote-asset documentation pages,
and marks API responses as non-cacheable.

Unexpected API exceptions return a generic error. Only the exception type is
logged at this boundary; exception messages and request/document values are not
written to the API log.

Uploads are streamed and limited by encoded byte size and decoded page pixel
count. Only validated PNG, JPEG, and readable unencrypted PDF files are
accepted. PDFs are also constrained by page count and are rasterized into
private page images before analysis. Reviewed PDF export reconstructs a new
image-only document and checks it for extractable text.

The application deletes a session workspace on explicit removal and deletes
remaining sessions on shutdown. This cleanup does not constitute guaranteed
secure erasure.

The local token and loopback boundary are not suitable hosted authentication.
A future hosted deployment requires the separate controls described in
ADR-0007.

---

## Availability and Denial of Service

ML models and high-DPI PDF rendering may consume substantial CPU and
memory.

Untrusted extremely large documents could cause resource exhaustion.

UI/server deployments enforce file-size, page-count, and page-pixel limits.
Further hosted deployments should also consider:

- timeout policies;
- worker isolation.

The current project is primarily designed for trusted local desktop
workflows.

---

## Password-Protected Documents

Encrypted/password-protected files require explicit handling.

The application should fail clearly rather than attempting unsafe or
ambiguous processing.

Future support should preserve the same redaction and reconstruction
principles.

---

## Reporting Security Problems

Do not publicly upload real sensitive documents to demonstrate a bug.

Security reports should include the minimum information necessary to
reproduce the problem and should use synthetic data wherever possible.

See:

`SECURITY.md`
