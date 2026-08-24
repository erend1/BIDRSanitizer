# ADR-0006: Verification Semantics and Limitations

**Status:** Accepted  
**Date:** 2026-08-24

## Context

A sanitizer should not assume that applying a redaction once guarantees
that all target information has been removed.

Bounding boxes may be incomplete.

OCR may identify additional text after neighboring regions are removed.

Detectors may behave differently after redaction.

The project therefore requires an explicit verification stage.

However, machine-learning and OCR detectors are not formal proofs of
absence.

Using the same detector before and after sanitization introduces an
important blind spot: a detector that misses information initially may
also miss the same information during verification.

The meaning of a successful verification result must therefore be
precise and limited.

## Decision

After redaction, BIDR Sanitizer reruns the configured detector families
against the sanitized output.

A verification result passes only when no remaining target detections are
reported by the configured verifier.

The system may perform multiple redaction and verification passes, up to
the configured maximum.

For image remediation, accumulated detections are applied against the
original image rather than repeatedly recompressing or modifying the
previous redacted output.

If verification continues to report only detections already represented
in the accumulated redaction set and no additional remediation is
possible, processing may stop and require review rather than looping
indefinitely.

## Meaning of PASS

`PASS` means:

> No configured BIDR Sanitizer verification detector found remaining
> target PII in the sanitized output.

`PASS` does not mean:

> The document has been mathematically proven to contain no sensitive
> information.

`PASS` is not a legal conclusion.

`PASS` is not a guarantee of KVKK, GDPR, HIPAA, contractual, regulatory,
or institutional compliance.

`PASS` does not eliminate the need for human review in workflows where
the consequences of disclosure are significant.

## Known limitation

The verifier may share failure modes with the initial detector.

A target that is missed during detection may also be missed during
verification.

This is an inherent limitation of detector-based verification.

BIDR Sanitizer mitigates this risk through:

- high-recall detector configuration
- multiple detector families
- deterministic recognizers where applicable
- synthetic regression fixtures
- repeated verification
- destructive redaction
- human visual review

These measures reduce risk but do not convert detector output into a
formal proof.

## Regression testing

Synthetic fixtures should intentionally contain representative examples
of all supported target categories.

At minimum, regression coverage should include:

    TCKN
    Turkish phone numbers
    email addresses
    person names
    addresses
    faces
    signatures

Known detector failures should be preserved as regression cases whenever
practical.

A verifier regression should be considered security-relevant even if
ordinary unit tests still pass.

## Manual overrides

A future UI may allow users to remove automatically generated masks.

Such an action changes the provenance of the output.

If a user intentionally overrides an automatic privacy decision, the UI
must not silently present the ordinary automatic PASS semantics without
making that override visible.

Human override and automatic verification are distinct concepts.