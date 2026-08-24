# Security Policy

BIDR Sanitizer is a privacy-oriented document sanitization framework.

Security reports are taken seriously because failures may affect the
confidentiality of documents containing personally identifiable
information or other sensitive content.

## Supported versions

The latest released `0.1.x` version is supported for security fixes.

Older pre-release builds, development snapshots, and unmaintained
branches may not receive security updates.

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Older versions | No |

## Reporting a vulnerability

Please do not report security vulnerabilities through a public GitHub
issue.

Once GitHub Private Vulnerability Reporting is enabled for the
repository, use the repository's **Security** tab and choose
**Report a vulnerability**.

This allows vulnerability details to remain private while maintainers
investigate the report.

Do not include real personal, confidential, or institutional documents
unless doing so has been explicitly agreed with the maintainers.

Synthetic reproductions are strongly preferred.

## What to report privately

Examples of issues that should be reported privately include:

- sensitive content remaining recoverable after redaction
- reversible or removable visual masking
- original PDF text or hidden content surviving sanitized reconstruction
- raw detected PII appearing in logs, audit output, exceptions, or
  telemetry
- unintended transmission of document content to external services
- unintended model downloads during document sanitization
- temporary-file handling that exposes sensitive document content
- path traversal or arbitrary file overwrite vulnerabilities
- unsafe handling of untrusted DOC or DOCX input
- vulnerabilities in model-loading or model-path handling
- malicious model or dependency supply-chain concerns
- verifier behavior that incorrectly reports successful sanitization in
  a reproducible security-relevant scenario
- secrets, credentials, or sensitive repository artifacts accidentally
  included in a release

Ordinary detector accuracy improvements that do not demonstrate a
security-relevant failure may be reported as normal bug reports using
synthetic data.

## Information to include

A useful security report should contain:

- affected BIDR Sanitizer version or commit
- operating system
- Python version
- affected input format
- affected detector or pipeline, if known
- minimal steps to reproduce
- expected behavior
- observed behavior
- security or privacy impact
- synthetic reproduction files where possible
- relevant dependency and model versions

Do not include raw personal information in logs or example values.

## Response process

After receiving a report, maintainers will attempt to:

1. acknowledge the report
2. reproduce and assess the issue
3. determine affected versions and components
4. develop and test a remediation
5. prepare a coordinated release when appropriate
6. document the security impact without unnecessarily exposing sensitive
   reproduction material

Response times are best-effort and may vary according to severity and
maintainer availability.

## Disclosure

Please allow maintainers reasonable time to investigate and release a
fix before publicly disclosing vulnerability details.

Security advisories should avoid publishing real sensitive documents or
personal information.

## Security model

BIDR Sanitizer is designed around several security and privacy
principles:

- offline-first document processing
- local model inference
- no silent runtime model downloads
- explicit, pinned, hash-verified model installation through a separate
  `bidr-models install` command
- destructive opaque visual redaction
- separation of detection and redaction
- image-only PDF reconstruction
- no raw detected PII in audit output
- post-redaction verification
- synthetic regression testing
- explicit handling of known detector limitations

See:

- `docs/PRIVACY_AND_SECURITY.md`
- `docs/ARCHITECTURE.md`
- `docs/adr/`

for the detailed architecture and threat model.

## Verification limitations

A BIDR Sanitizer `PASS` result means that no configured verification
detector found remaining target PII in the sanitized output.

It is not a mathematical proof that no sensitive information remains.

It is not a legal or regulatory compliance determination.

The verifier may share failure modes with the detector used before
redaction. Human review remains appropriate for workflows where
disclosure consequences are significant.

## Third-party vulnerabilities

BIDR Sanitizer depends on third-party libraries and external local model
assets.

If a vulnerability exists exclusively in an upstream dependency,
reporting it to the upstream project may also be appropriate.

If the vulnerability becomes exploitable specifically because of how
BIDR Sanitizer configures or invokes that dependency, please also report
it privately to BIDR Sanitizer maintainers.

Third-party licenses and model identities are documented in:

- `THIRD_PARTY_NOTICES.md`
- `models/manifest.json`

## Privacy of security reports

Security reports themselves may contain sensitive technical information.

Do not submit credentials, access tokens, passwords, real identity
documents, or unnecessary personal data.

Use synthetic examples wherever possible.
