from pathlib import Path

from huggingface_hub import snapshot_download


TARGET = Path(
    r"C:\BIDRModels\signature"
) / "yolos-small-signature-detection"


TARGET.mkdir(
    parents=True,
    exist_ok=True,
)


path = snapshot_download(
    repo_id=(
        "mdefrance/"
        "yolos-small-signature-detection"
    ),
    local_dir=str(TARGET),
)


print(
    "Signature model stored at:",
    path,
)