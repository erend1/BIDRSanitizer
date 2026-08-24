# Known-Good Environments

This directory contains reproducibility snapshots for BIDR Sanitizer.

These files are not the primary dependency specification for the
project.

The authoritative package dependency declarations remain in
`pyproject.toml`.

Known-good environment files record dependency versions that were
successfully tested together on a specific platform and Python version.
They are intended to help maintainers reproduce a previously validated
runtime when upstream dependency resolution changes.

## Windows / Python 3.13

`known-good-win-py313.txt` records the dependency environment used for
the BIDR Sanitizer v0.1.0 release validation.

The environment was validated with:

- Windows
- Python 3.13
- `bidr-sanitizer[all]`
- local model inference
- PaddleOCR
- GLiNER
- YuNet face detection
- signature detection
- TXT sanitization
- image sanitization
- Unicode Windows paths
- PDF sanitization
- DOCX sanitization
- verification
- clean wheel installation

The snapshot should not be interpreted as a requirement that every
transitive dependency remain permanently pinned to these versions.

When dependency compatibility is investigated, this environment provides
a known working reference point.

## Updating a snapshot

Do not overwrite a known-good snapshot merely because newer packages are
available.

Create or update one only after the corresponding environment has been
tested end-to-end.

A dependency upgrade that changes model inference behavior should be
treated as more than a packaging-only change and should receive runtime
regression testing.