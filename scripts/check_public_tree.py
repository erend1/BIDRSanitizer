from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


SKIPPED_DIRECTORY_NAMES = {
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "output",
    "outputs",
    "tmp",
    "temp",
    "htmlcov",
    "node_modules",
    "coverage",
}


SENSITIVE_DIRECTORY_NAMES = {
    "private",
    "evidence",
    "evidences",
    "kanit",
    "kanitlar",
    "real_data",
    "real_documents",
}


FORBIDDEN_SUFFIXES = {
    ".onnx",
    ".safetensors",
    ".pdiparams",
    ".pdmodel",
    ".pfx",
    ".p12",
    ".pem",
    ".key",
}


ALLOWED_MODEL_FILES = {
    Path("models/README.md"),
    Path("models/manifest.json"),
}


def _is_skipped_directory_name(
    name: str,
) -> bool:
    normalized = name.lower()

    return (
        normalized in SKIPPED_DIRECTORY_NAMES
        or normalized.startswith(".venv-")
    )


def main() -> int:
    sensitive_directories: set[Path] = set()
    forbidden_files: list[Path] = []
    other_problems: list[str] = []

    for root, directories, files in os.walk(
        PROJECT_ROOT
    ):
        root_path = Path(root)

        # Prevent os.walk from descending into local/generated
        # development directories.
        directories[:] = [
            directory
            for directory in directories
            if not _is_skipped_directory_name(
                directory
            )
        ]

        relative_root = (
            root_path.relative_to(
                PROJECT_ROOT
            )
        )

        # Sensitive directories are different from ordinary skipped
        # directories: their presence is itself considered a failure.
        sensitive_components = [
            part
            for part in relative_root.parts
            if (
                part.lower()
                in SENSITIVE_DIRECTORY_NAMES
            )
        ]

        if sensitive_components:
            for index, part in enumerate(
                relative_root.parts
            ):
                if (
                    part.lower()
                    in SENSITIVE_DIRECTORY_NAMES
                ):
                    sensitive_root = Path(
                        *relative_root.parts[
                            : index + 1
                        ]
                    )

                    sensitive_directories.add(
                        sensitive_root
                    )

                    break

            directories[:] = []
            continue

        # Detect sensitive directories before descending into them.
        for directory in list(directories):
            if (
                directory.lower()
                in SENSITIVE_DIRECTORY_NAMES
            ):
                relative = (
                    relative_root
                    / directory
                )

                sensitive_directories.add(
                    relative
                )

                directories.remove(
                    directory
                )

        for filename in files:
            relative = (
                relative_root
                / filename
            )

            if (
                relative
                in ALLOWED_MODEL_FILES
            ):
                continue

            path = (
                PROJECT_ROOT
                / relative
            )

            if (
                path.suffix.lower()
                in FORBIDDEN_SUFFIXES
            ):
                forbidden_files.append(
                    relative
                )

    print(
        "=== BIDR SANITIZER PUBLIC TREE CHECK ==="
    )
    print()

    if sensitive_directories:
        print(
            "Sensitive directories:"
        )

        for directory in sorted(
            sensitive_directories,
            key=lambda item: str(
                item
            ).lower(),
        ):
            print(
                f"  [FAIL] {directory}"
            )

        print()

    if forbidden_files:
        print(
            "Forbidden binary/model files:"
        )

        for file_path in sorted(
            forbidden_files,
            key=lambda item: str(
                item
            ).lower(),
        ):
            print(
                f"  [FAIL] {file_path}"
            )

        print()

    if other_problems:
        print(
            "Other problems:"
        )

        for problem in other_problems:
            print(
                f"  [FAIL] {problem}"
            )

        print()

    problem_count = (
        len(sensitive_directories)
        + len(forbidden_files)
        + len(other_problems)
    )

    print("Summary:")
    print(
        "  Sensitive directories:",
        len(sensitive_directories),
    )
    print(
        "  Forbidden binary/model files:",
        len(forbidden_files),
    )
    print(
        "  Other problems:",
        len(other_problems),
    )
    print()

    if problem_count:
        print(
            "PUBLIC TREE CHECK FAILED"
        )
        return 1

    print(
        "PUBLIC TREE CHECK PASSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
