from pathlib import Path

from huggingface_hub import (
    snapshot_download,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

TARGET = (
    PROJECT_ROOT
    / "models"
    / "gliner"
    / "gliner_multi_pii_v1"
)


TARGET.mkdir(
    parents=True,
    exist_ok=True,
)


path = snapshot_download(
    repo_id="urchade/gliner_multi_pii-v1",
    local_dir=str(TARGET),
)


print(
    "GLiNER model stored at:",
    path,
)