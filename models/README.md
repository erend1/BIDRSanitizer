# BIDR Sanitizer Models


BIDR Sanitizer uses several local machine-learning models.


Model weights are intentionally **not stored in this Git repository**.


Advanced deployments may override the normal runtime model root through:


`BIDR_MODELS_DIR`


The default Windows installation path is:


`%LOCALAPPDATA%\BIDRSanitizer\models`


Install and verify the pinned model set with:


```powershell
bidr-models install
bidr-models check
```


Example custom layout:


```text
C:\BIDRModels\
├── paddleocr\
│   ├── PP-OCRv5_server_det\
│   └── latin_PP-OCRv5_mobile_rec\
├── gliner\
│   └── gliner_multi_pii_v1\
├── yunet\
│   └── face_detection_yunet_2023mar.onnx
└── signature\
    └── yolos-small-signature-detection\
```

## Why models are kept outside the repository

Keeping model weights separate:

prevents very large Git repositories;
allows models to be installed once and shared between environments;
makes offline deployment explicit;
prevents accidental redistribution of third-party model artifacts;
avoids native-library path problems encountered on Windows.

### Local models

BIDR Sanitizer performs model inference locally. Required model files
are not silently downloaded during sanitization.

The default Windows model directory is:

    %LOCALAPPDATA%\BIDRSanitizer\models

Most users do not need to configure a model path. Advanced users may
override the location with `BIDR_MODELS_DIR`.

See `docs/MODELS.md` for setup details.

### Windows path requirement

For maximum compatibility with Paddle's native inference runtime, the
resolved Windows model path must be ASCII-only.

Recommended:

C:\BIDRModels

Avoid paths containing characters such as Turkish İ, ş, ğ, etc.

During development, Paddle's Python layer could see models stored under a
Unicode path while Paddle's native inference layer reported the existing
inference.json file as missing.

### Offline operation

After required models have been installed locally, normal document
sanitization is designed to perform inference without downloading models
or sending document contents to hosted AI services.

Missing models should be treated as an installation error rather than
silently downloaded during normal application runtime.

See manifest.json for the model inventory.

`bidr-models install` is the only supported operation that downloads
models. It uses immutable revisions from the packaged manifest, verifies
required file sizes and SHA-256 hashes, and stages downloads before making
them available to normal runtime.

`bidr-models check` verifies the installed model set without performing a
download.
