from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
    transformers: TranslateTransformersConfig


@dataclass(frozen=True)
class AppConfig:
    tools: ToolConfig
    pipeline: PipelineConfig
    asr: ASRConfig
    translate: TranslateConfig


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


def _required_positive_float(value: object, field: str) -> float:
    parsed = float(value)
    if parsed <= 0.0:
        raise ValueError(f"Config field '{field}' must be > 0.")
    return parsed


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
            transformers=TranslateTransformersConfig(
                model_id=transformers_model_id,
                device=transformers_device,
                max_new_tokens=transformers_max_new_tokens,
                source_lang_code=source_lang_code,
                target_lang_code=target_lang_code,
            ),
        ),
    )
