$ErrorActionPreference = "Stop"

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath "pyproject.toml")) {
    throw "Run this script from the BIDRSanitizer repository root."
}

if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    throw "nvidia-smi was not found. An NVIDIA GPU and current driver are required."
}

& nvidia-smi
if ($LASTEXITCODE -ne 0) {
    throw "nvidia-smi could not communicate with the NVIDIA driver."
}

Invoke-Python -m pip install --force-reinstall --no-deps `
    "torch==2.13.0+cu130" `
    "torchvision==0.28.0+cu130" `
    --index-url "https://download.pytorch.org/whl/cu130"

# The CPU and GPU Paddle distributions expose the same Python package and
# must not remain installed together.
Invoke-Python -m pip uninstall --yes paddlepaddle
Invoke-Python -m pip install --force-reinstall `
    "paddlepaddle-gpu==3.2.2" `
    --index-url "https://www.paddlepaddle.org.cn/packages/stable/cu129/" `
    --extra-index-url "https://pypi.org/simple"

Invoke-Python -m pip check

$env:BIDR_INFERENCE_DEVICE = "gpu:0"
Invoke-Python scripts\check_gpu_runtime.py --device gpu:0

Write-Host "BIDR Sanitizer GPU runtime installation passed."
