# Image and PDF Review Workflow

## Purpose

The review application layer lets a user inspect automatic image
detections before BIDR Sanitizer destroys pixels in the exported artifact.

The current application supports PNG and JPEG images directly and PDF through
a page-raster adapter. Word and text review remain future adapters. All
formats must continue through centralized privacy engines rather than moving
sanitization into the UI.

The web frontend and desktop shell are separate application adapters. The
privacy contract documented here has no dependency on FastAPI, React, or a
desktop webview.

The current versioned FastAPI adapter is documented separately in
`WEB_API.md`; it depends on this contract, not the reverse.

---

## Data Flow

```text
source image
      |
      v
automatic analysis
      |
      v
ImageReviewPlan revision 0
      |
      v
review decisions and manual regions
      |
      v
ImageReviewPlan revision N
      |
      v
deterministic pixel export
      |
      v
verification of temporary output
      |
      v
atomic destination replacement
```

Preview rectangles are display-only. Only deterministic export permanently
overwrites the source pixels represented by retained plan regions.

For PDF, the private session renders every page to an image at the configured
review DPI. Each page follows the flow above with its own source binding and
plan revision. Export sanitizes and verifies every page, constructs a new
image-only PDF from the generated images, and rejects a result with
extractable text. Original PDF objects are never copied into the output.

---

## Contract Types

`ImageSanitizerSettings` currently contains only settings that the review
export actually supports:

- opaque redaction safety margin;
- maximum redaction passes.

Detector thresholds are intentionally not exposed as inactive UI settings.
Adding them requires detector configuration plumbing and privacy regression
evaluation.

`ImageReviewPlan` contains:

- a plan ID and revision;
- the source image SHA-256 and pixel dimensions;
- typed settings;
- geometry-only review regions.

`ReviewRegion` contains:

- a stable region ID;
- an original-image pixel bounding box;
- automatic or manual provenance;
- retain or remove action;
- detector category and confidence when applicable;
- whether an automatic region's geometry was changed by a reviewer.

It does not contain OCR text or a detected PII value.

---

## Source Binding and Revisions

A plan is valid for only the exact source bytes and dimensions analyzed.
Export checks both before processing and again before promoting the result.
Applying coordinates to a modified or different image raises
`PlanSourceMismatchError`.

Review changes are immutable. `revise_image_review_plan` returns a new plan
with an incremented revision and leaves the previous object unchanged.
Callers must supply the revision they reviewed. A stale write raises
`PlanRevisionConflictError`.

This provides the optimistic-concurrency rule the future HTTP API will use.

---

## Human Decisions

A manual addition is privacy-conservative. It becomes a normal destructive
redaction region during export.

Removing an automatic region is an explicit human override. Remediation does
not silently re-add a verifier detection of the same category that overlaps
that removal. The final verifier report remains visible to the caller.

Moving or resizing an automatic region is also an explicit human override.
The revised bounding box is still applied by deterministic export, and the
verifier still scans the resulting artifact. Manual regions may be moved or
resized without becoming an override because they are already explicit,
privacy-conservative additions.

Review state contains region categories and counts, not the detected strings.

---

## Export Status

`ReviewedImageExportResult.status` has three states:

| Status | Meaning |
| --- | --- |
| `passed` | The configured verifier found no remaining detections and no automatic region was removed or geometrically changed. |
| `verified_with_human_overrides` | The verifier found no remaining detections, but at least one automatic region was removed, moved, or resized. |
| `review_required` | The configured verifier still finds one or more detections. |

The result's `passed` property is deliberately true only for ordinary
`passed`. `detectors_clear` separately reports whether the configured
verifier currently finds anything.

None of these states is a legal guarantee or proof that every sensitive item
was detected.

---

## Python Application API

Long-lived applications should reuse one service so the local models are
initialized only once:

```python
from bidr_sanitizer.models import BoundingBox
from bidr_sanitizer.review import (
    ImageSanitizerSettings,
    ManualRegionRequest,
    ReviewAction,
    ReviewDecision,
    revise_image_review_plan,
)
from bidr_sanitizer.service import BIDRSanitizerService


service = BIDRSanitizerService()

plan = service.analyze_image_for_review(
    "source.png",
    settings=ImageSanitizerSettings(
        redaction_margin=5,
        max_redaction_passes=3,
    ),
)

reviewed_plan = revise_image_review_plan(
    plan,
    expected_revision=plan.revision,
    decisions=[
        ReviewDecision(
            region_id="auto-0001",
            action=ReviewAction.RETAIN,
        )
    ],
    manual_regions=[
        ManualRegionRequest(
            bbox=BoundingBox(100, 120, 240, 180),
        )
    ],
)

result = service.export_reviewed_image(
    "source.png",
    "source_REDACTED.png",
    reviewed_plan,
)

print(result.status.value)
```

The SHA-256 source binding is internal plan state and is excluded from the
plan representation to reduce accidental diagnostic disclosure.

---

## Output Safety

Reviewed export always redraws from the original source with the accumulated
regions. This avoids repeatedly compressing an already modified JPEG.

The candidate output is written to a temporary sibling file. Verification
runs on that file. The destination is replaced atomically only after the
workflow finishes, including a completed `review_required` result. If a
detector or verifier raises an exception, the temporary candidate is removed
and an existing destination remains untouched.

An artifact returned as `review_required` must not be represented or shared
as verified safe output.
