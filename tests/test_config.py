from pathlib import Path

import pytest

from video_translate.config import load_config


def test_load_config_applies_override(tmp_path: Path) -> None:
    override = tmp_path / "override.toml"
    override.write_text(
        "\n".join(
            [
                "[pipeline]",
                'workspace_dir = "custom_runs"',
                "audio_sample_rate = 22050",
                "",
                "[asr]",
                "beam_size = 3",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(override)

    assert config.pipeline.workspace_dir == Path("custom_runs")
    assert config.pipeline.audio_sample_rate == 22050
    assert config.asr.beam_size == 3
    assert config.translate.backend == "mock"
    assert config.translate.target_language == "tr"


def test_load_config_rejects_non_positive_values(tmp_path: Path) -> None:
    override = tmp_path / "invalid.toml"
    override.write_text(
        "\n".join(
            [
                "[pipeline]",
                "audio_channels = 0",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pipeline.audio_channels"):
        load_config(override)


def test_load_config_rejects_invalid_translate_ratio(tmp_path: Path) -> None:
    override = tmp_path / "invalid_translate.toml"
    override.write_text(
        "\n".join(
            [
                "[translate]",
                "min_length_ratio = 2.0",
                "max_length_ratio = 1.5",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="translate.max_length_ratio"):
        load_config(override)
