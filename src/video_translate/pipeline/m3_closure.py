from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from video_translate.config import AppConfig, TTSConfig, load_config
from video_translate.pipeline.m3 import M3Artifacts, run_m3_pipeline
from video_translate.pipeline.m3_espeak_tune import (
    M3EspeakTuningArtifacts,
    run_m3_espeak_tuning_automation,
)
from video_translate.pipeline.m3_prep import prepare_m3_tts_input


@dataclass(frozen=True)
class M3ClosureArtifacts:
    tts_input_json: Path
    selected_config_path: Path
    tuning_artifacts: M3EspeakTuningArtifacts | None
    m3_artifacts: M3Artifacts
    closure_report_json: Path


def _with_strict_tts_gate(config: AppConfig) -> AppConfig:
    strict_tts = TTSConfig(
        backend=config.tts.backend,
        sample_rate=config.tts.sample_rate,
        min_segment_seconds=config.tts.min_segment_seconds,
        mock_base_tone_hz=config.tts.mock_base_tone_hz,
        espeak_bin=config.tts.espeak_bin,
        espeak_voice=config.tts.espeak_voice,
        espeak_speed_wpm=config.tts.espeak_speed_wpm,
        espeak_pitch=config.tts.espeak_pitch,
        espeak_adaptive_rate_enabled=config.tts.espeak_adaptive_rate_enabled,
        espeak_adaptive_rate_min_wpm=config.tts.espeak_adaptive_rate_min_wpm,
        espeak_adaptive_rate_max_wpm=config.tts.espeak_adaptive_rate_max_wpm,
        espeak_adaptive_rate_max_passes=config.tts.espeak_adaptive_rate_max_passes,
        espeak_adaptive_rate_tolerance_seconds=config.tts.espeak_adaptive_rate_tolerance_seconds,
        max_duration_delta_seconds=config.tts.max_duration_delta_seconds,
        qa_max_postfit_segment_ratio=config.tts.qa_max_postfit_segment_ratio,
        qa_max_postfit_seconds_ratio=config.tts.qa_max_postfit_seconds_ratio,
        qa_fail_on_flags=True,
        qa_allowed_flags=config.tts.qa_allowed_flags,
    )
    return AppConfig(
        tools=config.tools,
        pipeline=config.pipeline,
        asr=config.asr,
        translate=config.translate,
        tts=strict_tts,
    )


def run_m3_closure_workflow(
    *,
    run_root: Path,
    target_lang: str = "tr",
    translation_output_json: Path | None = None,
    tts_input_json: Path | None = None,
    base_config_path: Path = Path("configs/profiles/gtx1650_espeak.toml"),
    tuned_output_config_path: Path = Path("configs/profiles/m3_espeak_recommended.toml"),
    auto_tune: bool = True,
    max_candidates: int = 16,
) -> M3ClosureArtifacts:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    resolved_target_lang = target_lang.strip() or "tr"

    resolved_translation_output = translation_output_json or (
        run_root / "output" / "translate" / f"translation_output.en-{resolved_target_lang}.json"
    )
    resolved_tts_input = tts_input_json or (
        run_root / "output" / "tts" / f"tts_input.{resolved_target_lang}.json"
    )
    prepare_m3_tts_input(
        translation_output_json_path=resolved_translation_output,
        output_json_path=resolved_tts_input,
        target_language=resolved_target_lang,
    )

    tuning_artifacts: M3EspeakTuningArtifacts | None = None
    selected_config = tuned_output_config_path
    if auto_tune:
        tuning_artifacts = run_m3_espeak_tuning_automation(
            run_root=run_root,
            tts_input_json=resolved_tts_input,
            base_config_path=base_config_path,
            output_config_path=tuned_output_config_path,
            max_candidates=max_candidates,
        )
        selected_config = tuning_artifacts.recommended_config_path
    elif not selected_config.exists():
        raise FileNotFoundError(
            f"Selected M3 config not found (auto_tune disabled): {selected_config}"
        )

    strict_config = _with_strict_tts_gate(load_config(selected_config))
    m3_output_json = run_root / "output" / "tts" / f"tts_output.{resolved_target_lang}.json"
    m3_qa_json = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest_json = run_root / "run_m3_manifest.json"
    m3_artifacts = run_m3_pipeline(
        tts_input_json_path=resolved_tts_input,
        output_json_path=m3_output_json,
        qa_report_json_path=m3_qa_json,
        run_manifest_json_path=m3_manifest_json,
        config=strict_config,
    )

    closure_report = run_root / "benchmarks" / "m3_closure_report.json"
    closure_report.parent.mkdir(parents=True, exist_ok=True)
    closure_report.write_text(
        json.dumps(
            {
                "stage": "m3_closure",
                "generated_at_utc": datetime.now(tz=UTC).isoformat(),
                "run_root": str(run_root),
                "target_lang": resolved_target_lang,
                "auto_tune": auto_tune,
                "tts_input_json": str(resolved_tts_input),
                "selected_config_path": str(selected_config),
                "strict_tts_gate_enabled": True,
                "tuning": {
                    "candidate_count": len(tuning_artifacts.generated_config_paths)
                    if tuning_artifacts
                    else 0,
                    "benchmark_report_json": (
                        str(tuning_artifacts.benchmark_report_json) if tuning_artifacts else None
                    ),
                    "tuning_report_markdown": (
                        str(tuning_artifacts.tuning_report_markdown) if tuning_artifacts else None
                    ),
                    "recommended_profile": (
                        tuning_artifacts.recommended_profile if tuning_artifacts else None
                    ),
                    "selection_report_json": (
                        str(tuning_artifacts.selection_report_json) if tuning_artifacts else None
                    ),
                },
                "m3_outputs": {
                    "tts_output_json": str(m3_artifacts.tts_output_json),
                    "qa_report_json": str(m3_artifacts.qa_report_json),
                    "run_manifest_json": str(m3_artifacts.run_manifest_json),
                    "stitched_preview_wav": str(m3_artifacts.stitched_preview_wav),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return M3ClosureArtifacts(
        tts_input_json=resolved_tts_input,
        selected_config_path=selected_config,
        tuning_artifacts=tuning_artifacts,
        m3_artifacts=m3_artifacts,
        closure_report_json=closure_report,
    )
