# Troubleshooting

This document records known installation and runtime problems encountered
during BIDR Sanitizer development.

# Local Models Are Missing or Incomplete

Run the full integrity check:

```powershell
bidr-models check
```

Install missing models explicitly:

```powershell
bidr-models install
```

If a final model directory already exists but is incomplete or corrupt,
the installer fails without replacing it. Request transactional repair:

```powershell
bidr-models install --repair
```

Normal sanitization never performs these downloads automatically.

---

# GLiNER Works Only When a Hugging Face Cache Already Exists

The GLiNER model requires tokenizer assets and the encoder configuration
from `microsoft/mdeberta-v3-base`. A legacy manual installation may
contain only `gliner_config.json` and `pytorch_model.bin`, causing
clean-cache offline startup to fail.

Run:

```powershell
bidr-models check
bidr-models install --repair
```

The verified installation includes `config.json`, `spm.model`, and
`tokenizer_config.json` in the GLiNER model directory. The runtime adapter
injects the local encoder configuration in memory; it does not rewrite the
installed, hash-checked files.

---

## Dependency compatibility

If a new installation begins failing after upstream dependency changes,
compare it with the known-good environment snapshots under
`requirements/`.

For the v0.1.0 Windows reference environment, see:

`requirements/known-good-win-py313.txt`

These snapshots are debugging and reproducibility references.
`pyproject.toml` remains the authoritative package dependency
specification.

Do not automatically downgrade dependencies solely because versions
differ from a snapshot. First identify whether the difference is related
to the observed failure.

---

# PaddlePaddle: `ConvertPirAttribute2RuntimeAttribute`

## Symptom

PaddleOCR initialization or inference fails on Windows with an error
similar to:

```text
NotImplementedError:
ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]
```

## Known Cause

This occurred with:

```text
PaddlePaddle 3.3.0
```

in the project's Windows CPU environment.

## Known-Good Version

```text
PaddlePaddle 3.2.2
```

## Fix

Inside the active virtual environment:

```powershell
python -m pip install --force-reinstall "paddlepaddle==3.2.2"
```

Then rerun the Paddle model smoke test.

Do not upgrade PaddlePaddle independently without integration testing.

---

# Paddle Reports Existing Model File as Missing

## Symptom

Python confirms that the local Paddle model files exist, but Paddle's
native inference runtime reports that an `inference.json` or related file
cannot be found.

## Likely Cause

The model is stored under a Windows path containing non-ASCII characters.

This project encountered the problem under a path containing:

```text
RUMELİ
```

## Fix

Move the model installation to an ASCII-only path.

Recommended:

```text
C:\BIDRModels
```

Then configure:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

---

# Sanitizer Looks for Models in the Wrong Directory

## Symptom

An error contains an unexpected model path such as:

```text
C:\models\...
```

instead of the intended model root.

## Diagnose

Run:

```powershell
echo $env:BIDR_MODELS_DIR
```

Then:

```powershell
python -c "import os; print(os.environ.get('BIDR_MODELS_DIR'))"
```

And:

```powershell
python -c "from bidr_sanitizer.config import MODELS_DIR; print(MODELS_DIR)"
```

## Fix

Configure the model root for the current shell:

```powershell
$env:BIDR_MODELS_DIR="C:\BIDRModels"
```

For a persistent user-level Windows setting:

```powershell
[Environment]::SetEnvironmentVariable(
    "BIDR_MODELS_DIR",
    "C:\BIDRModels",
    "User"
)
```

Open a new terminal afterward.

---

# Paddle Recognition Model Name Mismatch

## Symptom

Paddle attempts to initialize:

```text
PP-OCRv5_server_rec
```

even though the local directory contains:

```text
latin_PP-OCRv5_mobile_rec
```

## Cause

A custom model directory was provided without the matching explicit model
name.

## Fix

The adapter must specify both:

```python
text_recognition_model_name="latin_PP-OCRv5_mobile_rec"
```

and the matching local model directory.

Do not remove explicit Paddle model names from the adapter.

---

# Transformers mDeBERTa Regex Warning

## Symptom

GLiNER initialization prints a warning similar to:

```text
The tokenizer you are loading from
'microsoft/mdeberta-v3-base'
with an incorrect regex pattern...
```

## Current Status

This warning has not prevented correct GLiNER operation in the known-good
environment. In the pinned stack, the unmodified tokenizer matched the
canonical slow-tokenizer output for representative inputs; the suggested
Mistral-specific flag did not.

Do not automatically upgrade Transformers merely to silence this warning.

Upgrade only with semantic detector regression testing.

---

# `AutoImageProcessor requires the Torchvision library`

## Symptom

YOLOS signature detector initialization fails with:

```text
ImportError:
AutoImageProcessor requires the Torchvision library
```

## Fix

Install Torchvision compatible with the installed PyTorch version.

For a CPU-only environment, an example is:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Then verify:

```powershell
python -c "import torch, torchvision; print(torch.__version__, torchvision.__version__)"
```

---

# Face Detector Misses a Rotated Face

The current YuNet implementation evaluates:

```text
0°
90°
180°
270°
```

If a future refactor reintroduces rotation-related misses, verify that:

```text
rotation generation
coordinate mapping
bbox clamping
duplicate merging
```

are still functioning.

Do not conclude that verification is safe merely because the same detector
reports no remaining faces.

---

# Too Many Face Detections

Because multiple orientations are evaluated, the same physical face may be
detected more than once.

Duplicate detections should be merged using IoU and bbox union.

Do not simply increase the face confidence threshold to hide duplicates.

---

# Too Many Signature Detections

Some nearby or overlapping signature detections may refer to the same
physical signature.

The current signature detector merges appropriate duplicates.

Do not raise the threshold solely to reduce duplicate-looking outputs.

The project intentionally favors recall.

---

# `PermissionError` When Writing a PDF

## Symptom

ReportLab raises:

```text
PermissionError: [Errno 13] Permission denied
```

for an output such as:

```text
output\document_REDACTED.pdf
```

## Most Common Cause

The existing PDF is open in:

```text
Microsoft Edge
Adobe Acrobat Reader
Chrome
another PDF viewer
```

Windows may lock the file against replacement.

## Fix

Close the output PDF and rerun the sanitizer.

You can test the lock using:

```powershell
Remove-Item ".\output\document_REDACTED.pdf"
```

If removal also fails with access denied, the file is locked.

---

# PDF Is Much Larger Than the Original

This is expected.

The sanitizer reconstructs PDFs from rasterized sanitized page images.

A small source PDF may therefore become a much larger output.

The initial implementation intentionally prioritizes privacy and OCR
quality over aggressive compression.

---

# Text Cannot Be Selected in the Sanitized PDF

This is expected and intentional.

The final PDF is designed to be image-only.

Original searchable/selectable text is deliberately not preserved.

---

# PDF Verification Finds Extractable Text

The final rasterized PDF should normally contain no extractable original
text.

If:

```python
pdf_has_extractable_text(...)
```

returns `True`, treat the PDF as unsafe until the reason is understood.

Do not simply disable the check.

---

# DOC/DOCX Does Not Work

## Requirement

Microsoft Word must currently be installed and activated on Windows.

## Smoke Test

Try the standalone Word conversion path first.

If Word cannot be started, the error should indicate that Microsoft Word
is unavailable.

---

# Word Hangs or Shows a Dialog

The COM adapter should use:

```text
Visible=False
DisplayAlerts=False
ReadOnly=True
AddToRecentFiles=False
```

Unexpected dialogs may still occur for unusual or corrupted documents.

The current Word adapter is intended for local interactive workstation
use, not unattended server automation.

---

# DOC/DOCX Output Is PDF

This is intentional.

The privacy pipeline is:

```text
DOC/DOCX
   ↓
temporary PDF
   ↓
rasterized sanitizer
   ↓
new image-only PDF
```

The sanitizer does not currently reconstruct a sanitized editable Word
document.

---

# TXT Output Contains `[REDACTED]z`

Check the supplied span.

Text spans are end-exclusive:

```text
[start, end)
```

For example:

```python
text = "Ahmet Yılmaz"
```

should use:

```python
TextSpan(
    0,
    len(text),
)
```

when the entire string is sensitive.

---

# Public-Tree Checker Produces Thousands of Lines

The current checker should skip normal local/generated directories such
as:

```text
.venv
.pytest_cache
output
__pycache__
```

If an older checker recursively reports every file inside `.venv`, update
it to the current implementation.

Sensitive directories should be reported once rather than recursively.

---

# Model Weights Appear Under `models/`

The repository's `models/` directory should contain only:

```text
README.md
manifest.json
```

Actual weights belong in the external model directory.

Move them out before publishing.

---

# Models Try to Download During Runtime

This is not expected normal sanitizer behavior.

Verify that:

```text
BIDR_MODELS_DIR
```

points to a complete local model installation.

Also verify that adapters use:

```text
local_files_only=True
```

where appropriate and that required local paths are validated before
model initialization.

The desired behavior for missing models is:

```text
clear installation failure
```

not:

```text
automatic network download
```

---

# Tests Pass but a Real Sensitive Object Is Missed

This is possible.

Unit tests validate known behaviors but cannot cover every possible
detector blind spot.

Create a synthetic/non-sensitive regression fixture reproducing the miss,
then add:

```text
integration regression
unit test where applicable
documentation if architectural
```

before adjusting thresholds or detector logic.

Do not include a real person's private document in the public repository.

---

# `VERIFICATION: PASSED` but Something Is Still Visible

This indicates a detector blind spot.

The verifier uses the configured detector families and can therefore miss
the same item as the initial detector.

Do not treat this as merely a UI issue.

The correct response is to improve the detection strategy and create a
regression case.

The four-rotation face implementation was introduced after exactly this
class of problem.

---

# Need More Diagnostic Information

Safe diagnostic information includes:

```text
software versions
operating system
file format
model directory paths
detector type
confidence
bounding boxes
page number
traceback
```

Avoid posting:

```text
real names
real phone numbers
TCKNs
real addresses
real signatures
private document screenshots
```

in public GitHub issues.

Use synthetic reproduction data wherever possible.
