from __future__ import annotations

import argparse
import sys

from collections.abc import Sequence
from pathlib import Path

from bidr_sanitizer.config import get_models_dir
from bidr_sanitizer.model_check import (
    check_local_models,
)
from bidr_sanitizer.model_installer import (
    ModelInstallationError,
    ModelInstaller,
)
from bidr_sanitizer.model_manifest import (
    ModelManifestError,
    load_model_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidr-models",
        description=(
            "Explicitly install and verify BIDR Sanitizer's "
            "offline model files."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    install_parser = subparsers.add_parser(
        "install",
        help=(
            "Download pinned model files and verify their "
            "integrity before activation."
        ),
    )
    install_parser.add_argument(
        "--models-dir",
        type=Path,
        help=(
            "Installation root. Defaults to BIDR_MODELS_DIR "
            "or the per-user application-data directory."
        ),
    )
    install_parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "Transactionally replace existing incomplete or "
            "corrupt standard model directories."
        ),
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Verify the local model installation.",
    )
    check_parser.add_argument(
        "--models-dir",
        type=Path,
        help=(
            "Model root. Defaults to BIDR_MODELS_DIR or the "
            "per-user application-data directory."
        ),
    )
    check_parser.add_argument(
        "--quick",
        action="store_true",
        help=(
            "Check required files and sizes without computing "
            "SHA-256 hashes."
        ),
    )

    return parser


def _selected_models_dir(
    requested: Path | None,
) -> Path:
    return Path(
        requested
        if requested is not None
        else get_models_dir()
    ).expanduser().resolve()


def _format_bytes(value: int) -> str:
    gibibytes = value / (1024**3)
    return f"{value:,} bytes ({gibibytes:.2f} GiB)"


def _run_check(
    models_dir: Path,
    *,
    quick: bool,
) -> int:
    statuses = check_local_models(
        models_dir,
        verify_hashes=not quick,
    )

    print(f"Model directory: {models_dir}")
    print(
        "Verification: "
        + (
            "required files and sizes"
            if quick
            else "required files, sizes, and SHA-256"
        )
    )
    print()

    for status in statuses:
        label = (
            "OK"
            if status.valid
            else status.state.upper()
        )
        print(f"[{label}] {status.name}")
        print(f"  {status.path}")

        for problem in status.problems:
            print(f"  - {problem}")

    valid = all(
        status.valid
        for status in statuses
    )
    print()
    print(
        "MODEL CHECK PASSED"
        if valid
        else "MODEL CHECK FAILED"
    )

    return 0 if valid else 1


def _run_install(
    models_dir: Path,
    *,
    repair: bool,
) -> int:
    manifest = load_model_manifest()

    print(f"Model directory: {models_dir}")
    print(
        "Expected verified model data: "
        f"{_format_bytes(manifest.expected_size)}"
    )
    print(
        "This explicit command may contact Hugging Face only "
        "to retrieve the pinned public model artifacts."
    )
    print()

    installer = ModelInstaller(
        models_dir=models_dir,
        manifest=manifest,
    )
    report = installer.install(
        repair=repair
    )

    for result in report.results:
        print(
            f"[{result.action.upper()}] "
            f"{result.name}"
        )
        print(f"  {result.path}")

    print()
    print("MODEL INSTALLATION PASSED")
    print(
        "Normal sanitization remains offline and does not "
        "invoke this installer."
    )

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    models_dir = _selected_models_dir(
        args.models_dir
    )

    try:
        if args.command == "check":
            return _run_check(
                models_dir,
                quick=args.quick,
            )

        if args.command == "install":
            return _run_install(
                models_dir,
                repair=args.repair,
            )

    except (
        ModelInstallationError,
        ModelManifestError,
        OSError,
    ) as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1

    parser.error(
        f"Unsupported command: {args.command}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
