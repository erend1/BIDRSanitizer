# BIDR Sanitizer Release Checklist

This checklist defines the minimum release process for BIDR Sanitizer.

A release should not be published merely because the package builds.

BIDR Sanitizer processes potentially sensitive documents, so runtime,
privacy, packaging, repository, model, and licensing checks are part of
the release process.

---

## 1. Release scope

- [ ] Release version has been selected.
- [ ] Release scope is understood.
- [ ] No unrelated feature work is included.
- [ ] Known security-sensitive architectural changes have corresponding
      tests and documentation.
- [ ] Relevant ADRs have been reviewed.
- [ ] `CHANGELOG.md` is updated.

For semantic versioning:

- PATCH: compatible fixes
- MINOR: compatible new functionality
- MAJOR: incompatible behavior or contract changes

The initial public release is `0.1.0`.

---

## 2. Source-tree safety

Run:

```powershell
python scripts/check_public_tree.py
```

Required result:

```text
Sensitive directories: 0
Forbidden binary/model files: 0
Other problems: 0

PUBLIC TREE CHECK PASSED
```

Confirm manually:

- [ ] no real evidence documents
- [ ] no real personal information
- [ ] no model weights
- [ ] no credentials
- [ ] no API keys
- [ ] no environment files
- [ ] no virtual environments
- [ ] no generated sanitized outputs
- [ ] no private logs
- [ ] no temporary files
- [ ] no institutionally confidential material

---

## 3. Automated tests

Run:

```powershell
python -m pytest -q
```

- [ ] All tests pass.
- [ ] Structured PII tests pass.
- [ ] OCR mapping tests pass.
- [ ] Semantic recognition tests pass.
- [ ] Face detection tests pass.
- [ ] Signature detection tests pass.
- [ ] Redaction tests pass.
- [ ] Verification tests pass.
- [ ] PDF tests pass.
- [ ] Word adapter tests pass.
- [ ] TXT tests pass.
- [ ] CLI tests pass.
- [ ] service lazy-loading tests pass.
- [ ] configuration tests pass.
- [ ] Unicode image-path regression passes.

---

## 4. Privacy regression

Run the synthetic mixed-PII fixture.

The fixture should exercise representative examples of:

- [ ] TCKN
- [ ] Turkish phone number
- [ ] email
- [ ] person name
- [ ] address
- [ ] face
- [ ] signature

Required:

- [ ] sanitization completes
- [ ] configured verifier reports zero remaining target detections
- [ ] output reports `PASS`
- [ ] visual redaction is opaque
- [ ] redaction is destructive rather than blur or pixelation
- [ ] no obvious target PII remains during manual visual review

A `PASS` result is not treated as an absolute privacy or compliance
guarantee.

---

## 5. Format integration

Using synthetic or otherwise safe inputs:

- [ ] TXT end-to-end sanitization passes.
- [ ] PNG/JPEG end-to-end sanitization passes.
- [ ] Unicode Windows image paths pass.
- [ ] PDF end-to-end sanitization passes.
- [ ] DOCX end-to-end sanitization passes.

Legacy DOC acceptance testing is optional unless DOC-specific behavior
has changed.

For reconstructed PDF output:

- [ ] page count is correct
- [ ] page appearance is readable
- [ ] redactions are present
- [ ] original searchable text is not retained
- [ ] BIDR Sanitizer has not introduced an extractable text layer

For Word input:

- [ ] source document remains unchanged
- [ ] final output is the expected sanitized PDF

---

## 6. Model configuration

Default Windows model location:

```text
%LOCALAPPDATA%\BIDRSanitizer\models
```

Verify:

- [ ] normal runtime works without `BIDR_MODELS_DIR`
- [ ] explicit `BIDR_MODELS_DIR` override still works
- [ ] missing models fail explicitly
- [ ] sanitization does not silently download models
- [ ] Paddle model paths are validated appropriately
- [ ] model files are not inside the repository
- [ ] model files are not inside the Python wheel

Expected model families:

- [ ] PaddleOCR detection
- [ ] PaddleOCR recognition
- [ ] GLiNER PII
- [ ] YuNet face detection
- [ ] YOLOS signature detection

---

## 7. Dependencies

Run:

```powershell
python -m pip check
```

Required:

```text
No broken requirements found.
```

Verify known critical versions or compatibility constraints in
`pyproject.toml`.

For the v0.1.0 reference environment, compare with:

```text
requirements/known-good-win-py313.txt
```

Do not modify dependency pins merely to obtain newer versions immediately
before release.

Runtime changes caused by model or inference dependency upgrades require
regression testing.

---

## 8. Third-party and model licensing

Review:

- [ ] `LICENSE`
- [ ] `THIRD_PARTY_NOTICES.md`
- [ ] `models/manifest.json`

Confirm:

- [ ] BIDR Sanitizer project license is Apache-2.0
- [ ] PaddleOCR source/model licensing recorded
- [ ] PaddlePaddle licensing recorded
- [ ] GLiNER source/model licensing recorded
- [ ] YuNet source and MIT license recorded
- [ ] signature model source/license recorded
- [ ] OpenCV notices recorded
- [ ] PyTorch notices recorded
- [ ] Transformers licensing recorded
- [ ] pypdfium2/PDFium notices recorded
- [ ] ReportLab licensing recorded
- [ ] pywin32 notices recorded
- [ ] no unreviewed model assets are distributed

If new dependencies or models were added, this review must be repeated
for those components.

---

## 9. Documentation

Review:

- [ ] `README.md`
- [ ] `docs/INSTALLATION.md`
- [ ] `docs/MODELS.md`
- [ ] `docs/USAGE.md`
- [ ] `docs/PIPELINES.md`
- [ ] `docs/ARCHITECTURE.md`
- [ ] `docs/PRIVACY_AND_SECURITY.md`
- [ ] `docs/TESTING.md`
- [ ] `docs/TROUBLESHOOTING.md`
- [ ] `docs/DEVELOPMENT.md`
- [ ] `docs/MAINTAINER_HANDOFF.md`
- [ ] `docs/adr/`
- [ ] `AGENTS.md`
- [ ] `CONTRIBUTING.md`
- [ ] `SECURITY.md`

Confirm documentation does not:

- [ ] claim `PASS` guarantees compliance
- [ ] claim perfect PII detection
- [ ] imply missing models are silently downloaded
- [ ] imply PDFs preserve their original text layer
- [ ] imply DOC/DOCX outputs remain editable Word documents
- [ ] expose private paths or sensitive information

---

## 10. Build distributions

Remove previous build artifacts:

```powershell
Remove-Item ".\build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item ".\src\bidr_sanitizer.egg-info" -Recurse -Force -ErrorAction SilentlyContinue
```

Build:

```powershell
python -m build
```

Required:

- [ ] wheel builds successfully
- [ ] source distribution builds successfully

---

## 11. Inspect wheel contents

Run:

```powershell
python -m zipfile -l `
    ".\dist\bidr_sanitizer-<VERSION>-py3-none-any.whl"
```

Confirm:

- [ ] expected Python modules are present
- [ ] CLI entry point metadata is present
- [ ] `LICENSE` is present
- [ ] required notice material is present
- [ ] no model weights are present
- [ ] no tests are unintentionally required at runtime
- [ ] no private files are present
- [ ] no local absolute paths are present

---

## 12. Inspect source distribution

Run:

```powershell
tar -tf `
    ".\dist\bidr_sanitizer-<VERSION>.tar.gz"
```

Confirm expected public engineering material is present:

- [ ] source
- [ ] tests
- [ ] documentation
- [ ] ADRs
- [ ] public scripts
- [ ] model metadata
- [ ] license and notices

Confirm:

- [ ] no model weights
- [ ] no private data
- [ ] no generated outputs
- [ ] no virtual environments

---

## 13. Clean-room base-wheel test

In a fresh virtual environment, install only the wheel without extras.

Verify:

- [ ] `import bidr_sanitizer`
- [ ] package version
- [ ] `bidr-sanitize --help`
- [ ] `python -m bidr_sanitizer --help`

The help commands must not require heavy optional runtime dependencies.

Actual sanitization without required extras/models must fail clearly
rather than crashing with an unrelated eager-import failure.

---

## 14. Clean-room full-runtime test

Create a new virtual environment.

Install:

```powershell
python -m pip install `
    ".\dist\bidr_sanitizer-<VERSION>-py3-none-any.whl[all]"
```

Run:

```powershell
python -m pip check
```

Verify:

- [ ] Paddle initializes
- [ ] GLiNER initializes
- [ ] complete image engine initializes
- [ ] default model directory resolves correctly
- [ ] representative TXT sanitization succeeds
- [ ] representative image sanitization succeeds
- [ ] representative PDF sanitization succeeds
- [ ] representative DOCX sanitization succeeds

---

## 15. Security

Review `SECURITY.md`.

Confirm:

- [ ] no public issue is recommended for vulnerabilities
- [ ] no personal maintainer email was accidentally exposed
- [ ] GitHub Private Vulnerability Reporting is enabled
- [ ] repository Security tab provides a private reporting route
- [ ] privacy/security limitations remain documented

---

## 16. Git repository audit

Before the release commit:

```powershell
git status --short
```

Review every listed file.

Then inspect ignored files:

```powershell
git status --short --ignored
```

Confirm virtual environments, models, outputs, and local artifacts are
ignored as expected.

Stage deliberately:

```powershell
git add .
```

Then inspect:

```powershell
git diff --cached --stat
git diff --cached
```

Do not commit until staged content has been reviewed.

---

## 17. GitHub repository

Confirm:

- [ ] repository description is correct
- [ ] repository visibility is correct
- [ ] default branch is `main`
- [ ] GitHub Actions workflow is present
- [ ] bug-report template is present
- [ ] feature-request template is present
- [ ] pull-request template is present
- [ ] Private Vulnerability Reporting is enabled
- [ ] repository topics are appropriate
- [ ] no placeholder URLs remain

Push and verify:

- [ ] first CI run passes
- [ ] README renders correctly
- [ ] issue templates render correctly
- [ ] license is recognized correctly by GitHub

---

## 18. Version and release

Before tagging:

- [ ] package version matches intended release
- [ ] `CHANGELOG.md` contains the release
- [ ] no `[Unreleased]` content intended for the release remains
      incorrectly categorized
- [ ] documentation references the correct version
- [ ] final CI run is green

Create the release tag only after these checks pass.

Example:

```text
v0.1.0
```

---

## 19. Post-release verification

After publication:

- [ ] release page renders correctly
- [ ] source archives contain only expected content
- [ ] installation instructions work from a new environment
- [ ] package metadata is correct
- [ ] security-reporting route remains available
- [ ] CI remains green

Do not delete the known-good environment or release artifacts until the
published release has been independently verified.