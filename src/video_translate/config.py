from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import tomllib


@dataclass(frozen=True)
class ToolConfig:
    yt_dlp: str
    ffmpeg: str


@dataclass(frozen=True)
class PipelineConfig:
    workspace_dir: Path
    audio_sample_rate: int
    audio_channels: int
    audio_codec: str


@dataclass(frozen=True)
class ASRConfig:
    model: str
    device: str
    compute_type: str
    beam_size: int
    language: str
    word_timestamps: bool
    vad_filter: bool
    fallback_on_oom: bool
    fallback_model: str
    fallback_device: str
    fallback_compute_type: str


@dataclass(frozen=True)
class TranslateTransformersConfig:
    model_id: str
    device: int
    max_new_tokens: int
    source_lang_code: str | None
    target_lang_code: str | None


@dataclass(frozen=True)
class TranslateConfig:
    backend: str
    source_language: str
    target_language: str
    batch_size: int
    min_length_ratio: float
    max_length_ratio: float
    glossary_path: Path | None
    glossary_case_sensitive: bool
    apply_glossary_postprocess: bool
    qa_check_terminal_punctuation: bool
    qa_check_long_segment_fluency: bool
    qa_long_segment_word_threshold: int
    qa_long_segment_max_pause_punct: int
    qa_fail_on_flags: bool
    qa_allowed_flags: tuple[str, ...]
    transformers: TranslateTransformersConfig


@dataclass(frozen=True)
class TTSConfig:
    backend: str
    sample_rate: int
    min_segment_seconds: float
    mock_base_tone_hz: int
    espeak_bin: str
    espeak_voice: str
    espeak_speed_wpm: int
    espeak_pitch: int
    espeak_adaptive_rate_enabled: bool
    espeak_adaptive_rate_min_wpm: int
    espeak_adaptive_rate_max_wpm: int
    espeak_adaptive_rate_max_passes: int
    espeak_adaptive_rate_tolerance_seconds: float
    max_duration_delta_seconds: float
    qa_max_postfit_segment_ratio: float
    qa_max_postfit_seconds_ratio: float
    qa_fail_on_flags: bool
    qa_allowed_flags: tuple[str, ...]
    piper_bin: str = "piper"
    piper_model_path: Path | None = None
    piper_config_path: Path | None = None
    piper_speaker: int | None = None
    piper_length_scale: float = 1.0
    piper_noise_scale: float = 0.667
    piper_noise_w: float = 0.8


@dataclass(frozen=True)
class AppConfig:
    tools: ToolConfig
    pipeline: PipelineConfig
    asr: ASRConfig
    translate: TranslateConfig
    tts: TTSConfig


def _required_non_empty_str(value: object, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"Config field '{field}' must be a non-empty string.")
    return normalized


def _required_positive_int(value: object, field: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"Config field '{field}' must be > 0.")
    return parsed


def _required_non_negative_int(value: object, field: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"Config field '{field}' must be >= 0.")
    return parsed


def _optional_str_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"Config field '{field}' must be a list of strings.")
    normalized: list[str] = []
    for index, item in enumerate(value):
        text = _required_non_empty_str(item, f"{field}[{index}]")
        normalized.append(text)
    return tuple(normalized)


def _required_positive_float(value: object, field: str) -> float:
    parsed = float(value)
    if parsed <= 0.0:
        raise ValueError(f"Config field '{field}' must be > 0.")
    return parsed


def _required_non_negative_float(value: object, field: str) -> float:
    parsed = float(value)
    if parsed < 0.0:
        raise ValueError(f"Config field '{field}' must be >= 0.")
    return parsed


def _resolve_binary_command(value: str, root: Path) -> str:
    normalized = value.strip()
    if (
        "/" not in normalized
        and "\\" not in normalized
        and not normalized.lower().endswith(".exe")
    ):
        return normalized

    candidate = Path(normalized)
    has_windows_drive = bool(PureWindowsPath(normalized).drive)
    if not candidate.is_absolute() and not has_windows_drive:
        candidate = root / candidate
    return str(candidate)


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a TOML table: {path}")
    return data


def load_config(config_path: Path | None = None) -> AppConfig:
    root = Path(__file__).resolve().parents[2]
    default_path = root / "configs" / "default.toml"
    data = _read_toml(default_path)

    if config_path is not None:
        override = _read_toml(config_path)
        data = _deep_merge(data, override)

    tools_table = data.get("tools", {})
    pipeline_table = data.get("pipeline", {})
    asr_table = data.get("asr", {})
    translate_table = data.get("translate", {})
    tts_table = data.get("tts", {})
    translate_transformers_table = translate_table.get("transformers", {})

    yt_dlp = _required_non_empty_str(tools_table.get("yt_dlp", "yt-dlp"), "tools.yt_dlp")
    ffmpeg = _required_non_empty_str(tools_table.get("ffmpeg", "ffmpeg"), "tools.ffmpeg")
    workspace_dir = _required_non_empty_str(
        pipeline_table.get("workspace_dir", "runs"), "pipeline.workspace_dir"
    )
    audio_sample_rate = _required_positive_int(
        pipeline_table.get("audio_sample_rate", 16000), "pipeline.audio_sample_rate"
    )
    audio_channels = _required_positive_int(
        pipeline_table.get("audio_channels", 1), "pipeline.audio_channels"
    )
    audio_codec = _required_non_empty_str(
        pipeline_table.get("audio_codec", "pcm_s16le"), "pipeline.audio_codec"
    )
    asr_model = _required_non_empty_str(asr_table.get("model", "medium"), "asr.model")
    asr_device = _required_non_empty_str(asr_table.get("device", "auto"), "asr.device")
    compute_type = _required_non_empty_str(
        asr_table.get("compute_type", "default"), "asr.compute_type"
    )
    beam_size = _required_positive_int(asr_table.get("beam_size", 5), "asr.beam_size")
    language = _required_non_empty_str(asr_table.get("language", "en"), "asr.language")
    fallback_model = _required_non_empty_str(
        asr_table.get("fallback_model", "small"), "asr.fallback_model"
    )
    fallback_device = _required_non_empty_str(
        asr_table.get("fallback_device", "cpu"), "asr.fallback_device"
    )
    fallback_compute_type = _required_non_empty_str(
        asr_table.get("fallback_compute_type", "int8"), "asr.fallback_compute_type"
    )
    translate_backend = _required_non_empty_str(
        translate_table.get("backend", "mock"), "translate.backend"
    )
    source_language = _required_non_empty_str(
        translate_table.get("source_language", "en"), "translate.source_language"
    )
    target_language = _required_non_empty_str(
        translate_table.get("target_language", "tr"), "translate.target_language"
    )
    translate_batch_size = _required_positive_int(
        translate_table.get("batch_size", 8), "translate.batch_size"
    )
    min_length_ratio = _required_positive_float(
        translate_table.get("min_length_ratio", 0.50), "translate.min_length_ratio"
    )
    max_length_ratio = _required_positive_float(
        translate_table.get("max_length_ratio", 1.80), "translate.max_length_ratio"
    )
    if max_length_ratio <= min_length_ratio:
        raise ValueError(
            "Config field 'translate.max_length_ratio' must be greater than "
            "'translate.min_length_ratio'."
        )

    transformers_model_id = _required_non_empty_str(
        translate_transformers_table.get("model_id", "Helsinki-NLP/opus-mt-en-tr"),
        "translate.transformers.model_id",
    )
    transformers_device = int(translate_transformers_table.get("device", -1))
    transformers_max_new_tokens = _required_positive_int(
        translate_transformers_table.get("max_new_tokens", 256),
        "translate.transformers.max_new_tokens",
    )
    source_lang_code_raw = translate_transformers_table.get("source_lang_code", None)
    target_lang_code_raw = translate_transformers_table.get("target_lang_code", None)
    source_lang_code = (
        _required_non_empty_str(source_lang_code_raw, "translate.transformers.source_lang_code")
        if source_lang_code_raw is not None
        else None
    )
    target_lang_code = (
        _required_non_empty_str(target_lang_code_raw, "translate.transformers.target_lang_code")
        if target_lang_code_raw is not None
        else None
    )
    glossary_raw = translate_table.get("glossary_path", None)
    glossary_path: Path | None
    if glossary_raw is None:
        glossary_path = None
    else:
        glossary_text = str(glossary_raw).strip()
        glossary_path = Path(glossary_text) if glossary_text else None
    if glossary_path is not None and not glossary_path.is_absolute():
        glossary_path = root / glossary_path
    glossary_case_sensitive = bool(translate_table.get("glossary_case_sensitive", False))
    apply_glossary_postprocess = bool(translate_table.get("apply_glossary_postprocess", True))
    qa_check_terminal_punctuation = bool(
        translate_table.get("qa_check_terminal_punctuation", True)
    )
    qa_check_long_segment_fluency = bool(
        translate_table.get("qa_check_long_segment_fluency", True)
    )
    qa_long_segment_word_threshold = _required_positive_int(
        translate_table.get("qa_long_segment_word_threshold", 14),
        "translate.qa_long_segment_word_threshold",
    )
    qa_long_segment_max_pause_punct = _required_non_negative_int(
        translate_table.get("qa_long_segment_max_pause_punct", 3),
        "translate.qa_long_segment_max_pause_punct",
    )
    qa_fail_on_flags = bool(translate_table.get("qa_fail_on_flags", False))
    qa_allowed_flags = _optional_str_tuple(
        translate_table.get("qa_allowed_flags", []),
        "translate.qa_allowed_flags",
    )
    tts_backend = _required_non_empty_str(tts_table.get("backend", "mock"), "tts.backend")
    if tts_backend not in {"mock", "espeak", "piper"}:
        raise ValueError(
            "Config field 'tts.backend' must be one of: mock, espeak, piper."
        )
    tts_sample_rate = _required_positive_int(tts_table.get("sample_rate", 24000), "tts.sample_rate")
    tts_min_segment_seconds = _required_positive_float(
        tts_table.get("min_segment_seconds", 0.12),
        "tts.min_segment_seconds",
    )
    tts_mock_base_tone_hz = _required_positive_int(
        tts_table.get("mock_base_tone_hz", 220),
        "tts.mock_base_tone_hz",
    )
    tts_espeak_bin = _required_non_empty_str(tts_table.get("espeak_bin", "espeak"), "tts.espeak_bin")
    tts_espeak_bin = _resolve_binary_command(tts_espeak_bin, root)
    tts_espeak_voice = _required_non_empty_str(tts_table.get("espeak_voice", "tr"), "tts.espeak_voice")
    tts_espeak_speed_wpm = _required_positive_int(
        tts_table.get("espeak_speed_wpm", 165),
        "tts.espeak_speed_wpm",
    )
    tts_espeak_pitch = _required_non_negative_int(
        tts_table.get("espeak_pitch", 50),
        "tts.espeak_pitch",
    )
    if tts_espeak_pitch > 99:
        raise ValueError("Config field 'tts.espeak_pitch' must be <= 99.")
    tts_espeak_adaptive_rate_enabled = bool(
        tts_table.get("espeak_adaptive_rate_enabled", True)
    )
    tts_espeak_adaptive_rate_min_wpm = _required_positive_int(
        tts_table.get("espeak_adaptive_rate_min_wpm", 120),
        "tts.espeak_adaptive_rate_min_wpm",
    )
    tts_espeak_adaptive_rate_max_wpm = _required_positive_int(
        tts_table.get("espeak_adaptive_rate_max_wpm", 260),
        "tts.espeak_adaptive_rate_max_wpm",
    )
    if tts_espeak_adaptive_rate_max_wpm < tts_espeak_adaptive_rate_min_wpm:
        raise ValueError(
            "Config field 'tts.espeak_adaptive_rate_max_wpm' must be >= "
            "'tts.espeak_adaptive_rate_min_wpm'."
        )
    tts_espeak_adaptive_rate_max_passes = _required_positive_int(
        tts_table.get("espeak_adaptive_rate_max_passes", 3),
        "tts.espeak_adaptive_rate_max_passes",
    )
    tts_espeak_adaptive_rate_tolerance_seconds = _required_non_negative_float(
        tts_table.get("espeak_adaptive_rate_tolerance_seconds", 0.06),
        "tts.espeak_adaptive_rate_tolerance_seconds",
    )
    tts_max_duration_delta_seconds = _required_non_negative_float(
        tts_table.get("max_duration_delta_seconds", 0.08),
        "tts.max_duration_delta_seconds",
    )
    tts_qa_max_postfit_segment_ratio = _required_non_negative_float(
        tts_table.get("qa_max_postfit_segment_ratio", 0.60),
        "tts.qa_max_postfit_segment_ratio",
    )
    if tts_qa_max_postfit_segment_ratio > 1.0:
        raise ValueError("Config field 'tts.qa_max_postfit_segment_ratio' must be <= 1.0.")
    tts_qa_max_postfit_seconds_ratio = _required_non_negative_float(
        tts_table.get("qa_max_postfit_seconds_ratio", 0.35),
        "tts.qa_max_postfit_seconds_ratio",
    )
    if tts_qa_max_postfit_seconds_ratio > 1.0:
        raise ValueError("Config field 'tts.qa_max_postfit_seconds_ratio' must be <= 1.0.")
    tts_qa_fail_on_flags = bool(tts_table.get("qa_fail_on_flags", False))
    tts_qa_allowed_flags = _optional_str_tuple(
        tts_table.get("qa_allowed_flags", []),
        "tts.qa_allowed_flags",
    )
    tts_piper_bin = _required_non_empty_str(tts_table.get("piper_bin", "piper"), "tts.piper_bin")
    tts_piper_bin = _resolve_binary_command(tts_piper_bin, root)
    tts_piper_model_raw = tts_table.get("piper_model_path", None)
    tts_piper_model_path: Path | None
    if tts_piper_model_raw is None:
        tts_piper_model_path = None
    else:
        model_text = str(tts_piper_model_raw).strip()
        tts_piper_model_path = Path(model_text) if model_text else None
    if tts_piper_model_path is not None and not tts_piper_model_path.is_absolute():
        tts_piper_model_path = root / tts_piper_model_path
    tts_piper_config_raw = tts_table.get("piper_config_path", None)
    tts_piper_config_path: Path | None
    if tts_piper_config_raw is None:
        tts_piper_config_path = None
    else:
        config_text = str(tts_piper_config_raw).strip()
        tts_piper_config_path = Path(config_text) if config_text else None
    if tts_piper_config_path is not None and not tts_piper_config_path.is_absolute():
        tts_piper_config_path = root / tts_piper_config_path
    tts_piper_speaker_raw = tts_table.get("piper_speaker", None)
    tts_piper_speaker: int | None
    if tts_piper_speaker_raw is None:
        tts_piper_speaker = None
    else:
        tts_piper_speaker = _required_non_negative_int(
            tts_piper_speaker_raw,
            "tts.piper_speaker",
        )
    tts_piper_length_scale = _required_positive_float(
        tts_table.get("piper_length_scale", 1.0),
        "tts.piper_length_scale",
    )
    tts_piper_noise_scale = _required_non_negative_float(
        tts_table.get("piper_noise_scale", 0.667),
        "tts.piper_noise_scale",
    )
    tts_piper_noise_w = _required_non_negative_float(
        tts_table.get("piper_noise_w", 0.8),
        "tts.piper_noise_w",
    )

    return AppConfig(
        tools=ToolConfig(
            yt_dlp=yt_dlp,
            ffmpeg=ffmpeg,
        ),
        pipeline=PipelineConfig(
            workspace_dir=Path(workspace_dir),
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
            audio_codec=audio_codec,
        ),
        asr=ASRConfig(
            model=asr_model,
            device=asr_device,
            compute_type=compute_type,
            beam_size=beam_size,
            language=language,
            word_timestamps=bool(asr_table.get("word_timestamps", True)),
            vad_filter=bool(asr_table.get("vad_filter", True)),
            fallback_on_oom=bool(asr_table.get("fallback_on_oom", True)),
            fallback_model=fallback_model,
            fallback_device=fallback_device,
            fallback_compute_type=fallback_compute_type,
        ),
        translate=TranslateConfig(
            backend=translate_backend,
            source_language=source_language,
            target_language=target_language,
            batch_size=translate_batch_size,
            min_length_ratio=min_length_ratio,
            max_length_ratio=max_length_ratio,
            glossary_path=glossary_path,
            glossary_case_sensitive=glossary_case_sensitive,
            apply_glossary_postprocess=apply_glossary_postprocess,
            qa_check_terminal_punctuation=qa_check_terminal_punctuation,
            qa_check_long_segment_fluency=qa_check_long_segment_fluency,
            qa_long_segment_word_threshold=qa_long_segment_word_threshold,
            qa_long_segment_max_pause_punct=qa_long_segment_max_pause_punct,
            qa_fail_on_flags=qa_fail_on_flags,
            qa_allowed_flags=qa_allowed_flags,
            transformers=TranslateTransformersConfig(
                model_id=transformers_model_id,
                device=transformers_device,
                max_new_tokens=transformers_max_new_tokens,
                source_lang_code=source_lang_code,
                target_lang_code=target_lang_code,
            ),
        ),
        tts=TTSConfig(
            backend=tts_backend,
            sample_rate=tts_sample_rate,
            min_segment_seconds=tts_min_segment_seconds,
            mock_base_tone_hz=tts_mock_base_tone_hz,
            espeak_bin=tts_espeak_bin,
            espeak_voice=tts_espeak_voice,
            espeak_speed_wpm=tts_espeak_speed_wpm,
            espeak_pitch=tts_espeak_pitch,
            espeak_adaptive_rate_enabled=tts_espeak_adaptive_rate_enabled,
            espeak_adaptive_rate_min_wpm=tts_espeak_adaptive_rate_min_wpm,
            espeak_adaptive_rate_max_wpm=tts_espeak_adaptive_rate_max_wpm,
            espeak_adaptive_rate_max_passes=tts_espeak_adaptive_rate_max_passes,
            espeak_adaptive_rate_tolerance_seconds=tts_espeak_adaptive_rate_tolerance_seconds,
            max_duration_delta_seconds=tts_max_duration_delta_seconds,
            qa_max_postfit_segment_ratio=tts_qa_max_postfit_segment_ratio,
            qa_max_postfit_seconds_ratio=tts_qa_max_postfit_seconds_ratio,
            qa_fail_on_flags=tts_qa_fail_on_flags,
            qa_allowed_flags=tts_qa_allowed_flags,
            piper_bin=tts_piper_bin,
            piper_model_path=tts_piper_model_path,
            piper_config_path=tts_piper_config_path,
            piper_speaker=tts_piper_speaker,
            piper_length_scale=tts_piper_length_scale,
            piper_noise_scale=tts_piper_noise_scale,
            piper_noise_w=tts_piper_noise_w,
        ),
    )
