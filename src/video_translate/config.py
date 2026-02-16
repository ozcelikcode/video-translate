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


@dataclass(frozen=True)
class TranslateTransformersConfig:
    model_id: str
    device: int
    max_new_tokens: int


@dataclass(frozen=True)
class TranslateConfig:
    backend: str
    source_language: str
    target_language: str
    batch_size: int
    min_length_ratio: float
    max_length_ratio: float
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
        ),
        translate=TranslateConfig(
            backend=translate_backend,
            source_language=source_language,
            target_language=target_language,
            batch_size=translate_batch_size,
            min_length_ratio=min_length_ratio,
            max_length_ratio=max_length_ratio,
            transformers=TranslateTransformersConfig(
                model_id=transformers_model_id,
                device=transformers_device,
                max_new_tokens=transformers_max_new_tokens,
            ),
        ),
    )
