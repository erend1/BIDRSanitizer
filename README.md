# BIDR Sanitizer

[![Tests](https://github.com/erend1/BIDRSanitizer/actions/workflows/tests.yml/badge.svg)](https://github.com/erend1/BIDRSanitizer/actions/workflows/tests.yml)

BIDR Sanitizer is an offline-first document privacy sanitization framework
for detecting and irreversibly redacting sensitive information from
institutional evidence documents.

The project was initially designed for BIDR/KIDR evidence workflows but
its sanitization engine is format-agnostic and can be used for other
document privacy workflows.

> **Project status:** Pre-release / active development.

## Supported Input Formats

- PNG
- JPEG
- PDF
- DOC
- DOCX
- TXT

DOC and DOCX conversion currently requires Microsoft Word on Windows.

## Detected Sensitive Information

The current sanitization pipeline supports:

- Turkish Republic identification numbers (TCKN)
- Turkish telephone numbers
- e-mail addresses
- person names
- home/postal addresses
- human faces
- handwritten signatures

## Core Design

BIDR Sanitizer follows a high-recall privacy model.

Machine-learning and deterministic detectors identify sensitive regions.
Actual redaction is performed by deterministic code that irreversibly
replaces the underlying information.

Sanitized outputs are scanned again using the same detection pipeline.
If sensitive information remains detectable, additional redaction passes
may be performed.

## Document Pipeline

Images are sanitized directly.

PDF documents are rendered into page images. Each page is sanitized and
verified before a completely new image-only PDF is generated.

DOC and DOCX documents are first converted to a temporary PDF using
Microsoft Word and then use the same PDF sanitization pipeline.

TXT files use character-span detection and replace sensitive values with
`[REDACTED]`.

## Offline-First Operation

Machine-learning models are installed locally.

After installing the complete runtime, retrieve the pinned model assets
with an explicit command:

```powershell
bidr-models install
bidr-models check
```

After model installation, normal inference is designed to operate without
sending document contents to hosted AI services.

Model files are not stored in this Git repository or Python wheel.
Normal sanitization never invokes the installer.

See:

`models/README.md`

## Verification Does Not Mean Legal Guarantee

A `PASSED` result means that the configured BIDR Sanitizer detectors found
no remaining detections in the sanitized output.

It does **not** guarantee that every possible item of sensitive information
has been identified, and it should not be interpreted as a legal guarantee
of anonymization or regulatory compliance.

Human review remains recommended for high-risk documents.

## Installation

Install the complete runtime for local use:

```powershell
python -m pip install "bidr-sanitizer[all]"
bidr-models install
bidr-models check
```

Detailed installation documentation is available in:

`docs/INSTALLATION.md`

## Usage

The project provides Python APIs and command-line interfaces for
sanitization and explicit model management.

Detailed examples are available in:

`docs/USAGE.md`

## Architecture

See:

`docs/ARCHITECTURE.md`

## Development

See:

- `CONTRIBUTING.md`
- `docs/DEVELOPMENT.md`
- `docs/TESTING.md`
- `AGENTS.md`

## License

BIDR Sanitizer is licensed under the Apache License 2.0.

Third-party packages and machine-learning models remain subject to their
respective licenses.

See:

`THIRD_PARTY_NOTICES.md`
