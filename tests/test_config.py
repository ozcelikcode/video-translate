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
    assert config.asr.fallback_on_oom is True
    assert config.asr.fallback_device == "cpu"
    assert config.translate.backend == "mock"
    assert config.translate.target_language == "tr"
    assert config.translate.glossary_path is not None
    assert config.translate.glossary_path.name == "glossary.en-tr.json"
    assert config.translate.qa_check_long_segment_fluency is True
    assert config.translate.qa_long_segment_word_threshold == 14
    assert config.translate.qa_long_segment_max_pause_punct == 3
    assert config.translate.qa_fail_on_flags is False
    assert config.translate.qa_allowed_flags == ()
    assert config.tts.backend == "mock"
    assert config.tts.sample_rate == 24000
    assert config.tts.min_segment_seconds == 0.12
    assert Path(config.tts.espeak_bin) == Path("C:/Program Files/eSpeak NG/espeak-ng.exe")
    assert config.tts.espeak_voice == "tr"
    assert config.tts.espeak_speed_wpm == 165
    assert config.tts.espeak_pitch == 50
    assert config.tts.espeak_adaptive_rate_enabled is True
    assert config.tts.espeak_adaptive_rate_min_wpm == 120
    assert config.tts.espeak_adaptive_rate_max_wpm == 260
    assert config.tts.espeak_adaptive_rate_max_passes == 3
    assert config.tts.espeak_adaptive_rate_tolerance_seconds == 0.06
    assert config.tts.max_duration_delta_seconds == 0.08
    assert config.tts.qa_max_postfit_segment_ratio == 0.60
    assert config.tts.qa_max_postfit_seconds_ratio == 0.35
    assert config.tts.piper_bin == "piper"
    assert config.tts.piper_model_path is None
    assert config.tts.piper_config_path is None
    assert config.tts.piper_speaker is None
    assert config.tts.piper_length_scale == 1.0
    assert config.tts.piper_noise_scale == 0.667
    assert config.tts.piper_noise_w == 0.8


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


def test_load_config_rejects_invalid_long_segment_threshold(tmp_path: Path) -> None:
    override = tmp_path / "invalid_long_segment.toml"
    override.write_text(
        "\n".join(
            [
                "[translate]",
                "qa_long_segment_word_threshold = 0",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="translate.qa_long_segment_word_threshold"):
        load_config(override)


def test_load_config_rejects_negative_pause_punct_limit(tmp_path: Path) -> None:
    override = tmp_path / "invalid_pause_limit.toml"
    override.write_text(
        "\n".join(
            [
                "[translate]",
                "qa_long_segment_max_pause_punct = -1",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="translate.qa_long_segment_max_pause_punct"):
        load_config(override)


def test_load_config_rejects_non_list_allowed_flags(tmp_path: Path) -> None:
    override = tmp_path / "invalid_allowed_flags.toml"
    override.write_text(
        "\n".join(
            [
                "[translate]",
                'qa_allowed_flags = "length_ratio_below_min_present"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="translate.qa_allowed_flags"):
        load_config(override)


def test_load_config_rejects_non_positive_tts_sample_rate(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_sr.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "sample_rate = 0",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.sample_rate"):
        load_config(override)


def test_load_config_rejects_negative_tts_duration_delta(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_delta.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "max_duration_delta_seconds = -0.01",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.max_duration_delta_seconds"):
        load_config(override)


def test_load_config_rejects_tts_pitch_above_max(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_pitch.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "espeak_pitch = 120",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.espeak_pitch"):
        load_config(override)


def test_load_config_rejects_tts_adaptive_rate_min_above_max(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_adaptive_range.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "espeak_adaptive_rate_min_wpm = 260",
                "espeak_adaptive_rate_max_wpm = 150",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.espeak_adaptive_rate_max_wpm"):
        load_config(override)


def test_load_config_rejects_non_positive_tts_adaptive_rate_passes(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_adaptive_passes.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "espeak_adaptive_rate_max_passes = 0",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.espeak_adaptive_rate_max_passes"):
        load_config(override)


def test_load_config_rejects_tts_postfit_segment_ratio_above_one(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_postfit_segment_ratio.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "qa_max_postfit_segment_ratio = 1.20",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.qa_max_postfit_segment_ratio"):
        load_config(override)


def test_load_config_rejects_tts_postfit_seconds_ratio_above_one(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_postfit_seconds_ratio.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "qa_max_postfit_seconds_ratio = 1.10",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.qa_max_postfit_seconds_ratio"):
        load_config(override)


def test_load_config_rejects_unsupported_tts_backend(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_backend.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                'backend = "invalid"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.backend"):
        load_config(override)


def test_load_config_rejects_non_positive_piper_length_scale(tmp_path: Path) -> None:
    override = tmp_path / "invalid_tts_piper_length_scale.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                "piper_length_scale = 0.0",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tts.piper_length_scale"):
        load_config(override)


def test_load_config_resolves_relative_piper_bin_path(tmp_path: Path) -> None:
    override = tmp_path / "piper_bin_relative.toml"
    override.write_text(
        "\n".join(
            [
                "[tts]",
                'backend = "piper"',
                'piper_bin = ".venv/Scripts/piper.exe"',
                'piper_model_path = "models/piper/tr_TR-dfki-medium.onnx"',
                'piper_config_path = "models/piper/tr_TR-dfki-medium.onnx.json"',
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(override)
    repo_root = Path(__file__).resolve().parents[1]
    assert config.tts.piper_bin == str(repo_root / ".venv" / "Scripts" / "piper.exe")
