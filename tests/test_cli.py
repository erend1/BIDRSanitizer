from __future__ import annotations

import pytest

from bidr_sanitizer.cli import main


def test_help_does_not_require_runtime_dependencies(
    capsys,
):
    with pytest.raises(
        SystemExit
    ) as exc_info:
        main(
            [
                "--help",
            ]
        )

    assert exc_info.value.code == 0

    output = capsys.readouterr()

    assert "bidr-sanitize" in output.out