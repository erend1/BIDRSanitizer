from pathlib import Path

from bidr_sanitizer import config


def test_explicit_model_directory_is_preferred(
    monkeypatch,
):
    expected = Path(
        r"C:\CustomBIDRModels"
    )

    monkeypatch.setenv(
        "BIDR_MODELS_DIR",
        str(expected),
    )

    assert (
        config.get_models_dir()
        == expected.resolve()
    )


def test_explicit_model_directory_is_preferred(
    monkeypatch,
    tmp_path,
):
    expected = (
        tmp_path
        / "models"
    )

    monkeypatch.setenv(
        "BIDR_MODELS_DIR",
        str(expected),
    )

    assert (
        config.get_models_dir()
        == expected.resolve()
    )


def test_default_model_directory_uses_app_data(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv(
        "BIDR_MODELS_DIR",
        raising=False,
    )

    monkeypatch.setenv(
        "LOCALAPPDATA",
        str(tmp_path),
    )

    assert (
        config.get_models_dir()
        == (
            tmp_path
            / "BIDRSanitizer"
            / "models"
        ).resolve()
    )


def test_default_paddle_cache_uses_app_data(
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv(
        "PADDLE_PDX_CACHE_HOME",
        raising=False,
    )

    monkeypatch.setenv(
        "LOCALAPPDATA",
        str(tmp_path),
    )

    assert (
        config.get_paddle_cache_dir()
        == (
            tmp_path
            / "BIDRSanitizer"
            / "paddlex_cache"
        ).resolve()
    )


def test_explicit_paddle_cache_is_preferred(
    monkeypatch,
    tmp_path,
):
    custom = (
        tmp_path
        / "custom_cache"
    )

    monkeypatch.setenv(
        "PADDLE_PDX_CACHE_HOME",
        str(custom),
    )

    assert (
        config.get_paddle_cache_dir()
        == custom.resolve()
    )


def test_ascii_path_detection():
    assert config.is_ascii_path(
        r"C:\BIDRModels"
    )

    assert not config.is_ascii_path(
        r"C:\RUMELİ\models"
    )